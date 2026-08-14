"""SRD 规则描述批量翻译（英文 → 中文）。

翻译对象：种族特性(traits)、职业 1-2 级特性(features)、专长(feats)。
- 批量：每批 5 条，LLM 返回 JSON {key: 译文}
- 断点续跑：translations 表已有 key 跳过
用法：python scripts/translate_srd.py
"""
import asyncio
import json
import os
import sqlite3
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app import db  # noqa: E402
from app.llm import stream_chat  # noqa: E402

DB_PATH = db.DB_PATH
BATCH = 5


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def collect_targets() -> dict:
    """收集 {key: 英文文本}。key 形如 traits:darkvision / feats:alert / features:second-wind。"""
    targets = {}

    # 1. 种族特性（traits 表全部）
    with _conn() as c:
        rows = c.execute("SELECT data FROM traits").fetchall()
    for r in rows:
        item = json.loads(r["data"])
        desc = (item.get("desc") or [])
        if desc:
            targets[f"traits:{item.get('index', '')}"] = "\n".join(desc)

    # 2. 职业 1-2 级特性（levels 表引用 features；level 列为 TEXT，必须 CAST 数值比较）
    with _conn() as c:
        levels = c.execute("SELECT data FROM levels WHERE CAST(level AS INTEGER) <= 2").fetchall()
    # features 表全量读入，按 index 建映射（name 列是大写，引用是小写 index）
    with _conn() as c:
        feat_rows = c.execute("SELECT data FROM features").fetchall()
    feat_by_index = {}
    for r in feat_rows:
        item = json.loads(r["data"])
        feat_by_index[item.get("index", "")] = item
    feat_indices = set()
    for r in levels:
        item = json.loads(r["data"])
        for f in item.get("features", []):
            feat_indices.add(f.get("index"))
    for idx in sorted(feat_indices):
        feat = feat_by_index.get(idx)
        if feat and feat.get("desc"):
            targets[f"features:{idx}"] = "\n".join(feat["desc"])

    # 3. 专长（feats 表全部，2024 版 description 字段）
    with _conn() as c:
        rows = c.execute("SELECT data FROM feats").fetchall()
    for r in rows:
        item = json.loads(r["data"])
        desc = item.get("description")
        if desc:
            targets[f"feats:{item.get('index', '')}"] = desc

    return targets


def load_done() -> set:
    with _conn() as c:
        rows = c.execute("SELECT key FROM translations").fetchall()
    return {r["key"] for r in rows}


def save_done(items: dict):
    with _conn() as c:
        c.executemany(
            "INSERT OR REPLACE INTO translations (key, zh) VALUES (?, ?)",
            [(k, v) for k, v in items.items()],
        )


async def translate_batch(batch: dict) -> dict:
    """一次请求翻译一批，LLM 返回 JSON {key: 译文}。"""
    lines = "\n".join(f"[{k}]\n{v}\n" for k, v in batch.items())
    prompt = (
        "你是《龙与地下城 5e》官方规则中文翻译专家。把以下英文规则文本翻译成简体中文：\n"
        "- 术语用国内通译（如 Darkvision→黑暗视觉、Proficiency Bonus→熟练加值）\n"
        "- 保留原文格式标记（**粗体**、换行）\n"
        f"- 只输出一个 JSON 对象，键为方括号中的 key，值为译文\n\n{lines}"
    )
    messages = [{"role": "user", "content": prompt}]
    out = ""
    async for evt in stream_chat(messages, max_tokens=1200):
        if evt["type"] == "delta":
            out += evt["text"]
    # 提取 JSON（容错：LLM 可能带 ```json 围栏）
    out = out.strip()
    if out.startswith("```"):
        out = out.split("```", 2)[1]
        if out.startswith("json"):
            out = out[4:]
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        print(f"  ⚠️ 解析失败，重试单条: {list(batch.keys())[:2]}", flush=True)
        results = {}
        for k, v in batch.items():
            single = await translate_batch({k: v})
            results.update(single)
        return results


async def main():
    with _conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS translations (key TEXT PRIMARY KEY, zh TEXT)")
    targets = collect_targets()
    done = load_done()
    todo = {k: v for k, v in targets.items() if k not in done}
    print(f"共 {len(targets)} 条，已完成 {len(done)}，待翻译 {len(todo)}")
    if not todo:
        print("全部已翻译")
        return

    keys = list(todo.keys())
    for i in range(0, len(keys), BATCH):
        batch = {k: todo[k] for k in keys[i:i + BATCH]}
        try:
            results = await translate_batch(batch)
            # 只保存成功返回的 key，缺失的下一轮重试
            valid = {k: v for k, v in results.items() if k in todo}
            save_done(valid)
            print(f"  [{i + len(valid)}/{len(todo)}] 批完成: {list(valid.keys())[:3]}...", flush=True)
        except Exception as e:
            print(f"  ❌ 批失败 {list(batch.keys())[:2]}: {e}", flush=True)
    print("完成")


if __name__ == "__main__":
    asyncio.run(main())
