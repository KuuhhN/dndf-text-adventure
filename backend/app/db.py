"""SQLite 访问层：5e SRD 规则数据查询（只读）。"""
import json
import os
import sqlite3

DB_PATH = os.environ.get(
    "DNDF_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "dndf.db"),
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_item(table: str, name: str) -> dict | None:
    """按精确名称查一条规则数据，返回解析后的 dict。"""
    with _conn() as c:
        row = c.execute(f'SELECT data FROM "{table}" WHERE name = ?', (name,)).fetchone()
    return json.loads(row["data"]) if row else None


def list_names(table: str) -> list[str]:
    with _conn() as c:
        rows = c.execute(f'SELECT name FROM "{table}" ORDER BY name').fetchall()
    return [r["name"] for r in rows]


def search(table: str, query: str, limit: int = 10) -> list[dict]:
    """按名称模糊搜索，返回 {name, data} 列表。"""
    with _conn() as c:
        rows = c.execute(
            f'SELECT name, data FROM "{table}" WHERE name LIKE ? ORDER BY name LIMIT ?',
            (f"%{query}%", limit),
        ).fetchall()
    return [{"name": r["name"], "data": json.loads(r["data"])} for r in rows]


# 常用快捷查询
def get_race(name): return get_item("races", name)
def get_class(name): return get_item("classes", name)
def get_spell(name): return get_item("spells", name)
def get_monster(name): return get_item("monsters", name)
def get_equipment(name): return get_item("equipment", name)
def list_races(): return list_names("races")
def list_classes(): return list_names("classes")


def get_zh(kind: str, index: str) -> str | None:
    """查询翻译：kind 形如 traits/features/feats。"""
    with _conn() as c:
        row = c.execute("SELECT zh FROM translations WHERE key = ?", (f"{kind}:{index}",)).fetchone()
    return row["zh"] if row else None


def _by_index(table: str, index: str) -> dict | None:
    """按 data JSON 内的 index 字段查条目（traits/features 的引用是小写 index，name 列是大写）。"""
    with _conn() as c:
        row = c.execute(
            f'SELECT data FROM "{table}" WHERE json_extract(data, "$.index") = ?',
            (index,),
        ).fetchone()
    return json.loads(row["data"]) if row else None


def _trait_detail(index: str) -> dict:
    """特性详情（名称 + 一句话用途 + 完整中文描述，无翻译时回退英文）。"""
    item = _by_index("traits", index) or _by_index("features", index)
    if not item:
        return {"index": index, "name": index, "desc": "", "summary": "", "zh": False}
    zh = get_zh("traits", index) or get_zh("features", index)
    summary = get_zh("sum:traits", index) or get_zh("sum:features", index) or ""
    return {
        "index": index,
        "name": item.get("name", index),
        "desc": zh or "\n".join(item.get("desc") or []),
        "summary": summary,
        "zh": zh is not None,
    }


def get_race_detail(name: str) -> dict | None:
    """种族详情：基础信息 + 特性（中文描述）。"""
    race = get_race(name)
    if not race:
        return None
    traits = [_trait_detail(t["index"]) for t in race.get("traits", [])]
    bonuses = [{"ability": ab["ability_score"]["name"], "bonus": ab.get("bonus", 0)}
               for ab in race.get("ability_bonuses", [])]
    return {
        "name": race.get("name"),
        "size": race.get("size"),
        "speed": race.get("speed"),
        "ability_bonuses": bonuses,
        "languages": race.get("languages", ""),
        "traits": traits,
        "subraces": [s.get("name") for s in race.get("subraces", [])],
    }


def get_class_detail(name: str) -> dict | None:
    """职业详情：生命骰/熟练/技能选项/1-2 级特性（中文描述）。"""
    cls = get_class(name)
    if not cls:
        return None
    # 等级特性：levels 表（class index 在 data JSON 内）
    with _conn() as c:
        rows = c.execute(
            "SELECT data FROM levels WHERE json_extract(data, '$.class.index') = ? AND level <= 2 ORDER BY level",
            (cls.get("index"),),
        ).fetchall()
    level_features = {}
    for r in rows:
        item = json.loads(r["data"])
        lv = item.get("level")
        level_features[lv] = [
            {"index": f["index"], "name": f["name"], **{k: v for k, v in _trait_detail(f["index"]).items() if k in ("desc",)}}
            for f in item.get("features", [])
        ]
    from .character import class_skill_choices
    return {
        "name": cls.get("name"),
        "hit_die": cls.get("hit_die"),
        "saving_throws": [s.get("name") for s in cls.get("saving_throws", [])],
        "proficiencies": [p.get("name") for p in cls.get("proficiencies", [])][:12],
        "skill_choices": class_skill_choices(name),
        "level_features": level_features,
    }


def get_feats(level: int = 1) -> list[dict]:
    """1 级可选专长（2024 SRD：origin/general 且 minimum_level<=1，含中文描述）。

    ponytail: 创建向导只展示 1 级能选的专长；4 级专长（ASI/Grappler）与
    史诗赐福（epic-boon）不在此列，避免"1 级看到 4 级内容"的困惑。
    """
    with _conn() as c:
        rows = c.execute("SELECT data FROM feats ORDER BY name").fetchall()
    out = []
    for r in rows:
        item = json.loads(r["data"])
        idx = item.get("index", "")
        prereq = item.get("prerequisites") or {}
        min_lv = prereq.get("minimum_level", 1) if isinstance(prereq, dict) else 1
        if item.get("type") not in ("origin", "general") or min_lv > level:
            continue
        zh = get_zh("feats", idx)
        summary = get_zh("sum:feats", idx) or ""
        out.append({
            "index": idx,
            "name": item.get("name", idx),
            "type": item.get("type", ""),
            "prerequisites": prereq,
            "desc": zh or item.get("description", ""),
            "summary": summary,
            "zh": zh is not None,
        })
    return out


def get_backgrounds() -> list[dict]:
    """全部背景（2024 SRD）。"""
    with _conn() as c:
        rows = c.execute("SELECT data FROM backgrounds ORDER BY name").fetchall()
    out = []
    for r in rows:
        item = json.loads(r["data"])
        out.append({
            "index": item.get("index", ""),
            "name": item.get("name", r["data"][:30]),
            "ability_scores": [a.get("name") for a in item.get("ability_scores", [])],
            "feat": (item.get("feat") or {}).get("name", ""),
            "proficiencies": [p.get("name") for p in item.get("proficiencies", [])],
            "skill_choices": [o.get("name") for o in
                              (item.get("proficiency_choices") or [{}])[0].get("from", {}).get("options", [])]
                              if item.get("proficiency_choices") else [],
        })
    return out
