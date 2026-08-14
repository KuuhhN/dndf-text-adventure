# -*- coding: utf-8 -*-
"""收集前端会显示的缺失 ZH 名称：9 种族 traits + 12 职业 1-2 级特性。

输出缺失清单到 stdout，供人工补 ZH 映射。
"""
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "data" / "5e-database" / "src" / "2014" / "en"

# 1. 前端 ZH 表（从 App.jsx 提取所有键）
jsx = (BASE.parent / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
zh_block = re.search(r"const ZH = \{.*?\};", jsx, re.S).group(0)
keys = set()
for m in re.finditer(r"(?:^\s*|,)\s*[\"\']?([A-Za-z][A-Za-z0-9 _\'\"]*?)[\"\']?\s*:", zh_block, re.M):
    k = m.group(1).strip('"\'')
    if k and not k.startswith("//"):
        keys.add(k)

# 2. 收集数据里会被界面展示的名称（不依赖 db 层，直接读源 JSON）
names = set()
races = json.loads((SRC / "5e-SRD-Races.json").read_text(encoding="utf-8"))
for r in races:
    names.update(t.get("name", "") for t in r.get("traits", []))
classes = json.loads((SRC / "5e-SRD-Classes.json").read_text(encoding="utf-8"))
class_index = {c["name"]: c.get("index", "") for c in classes}
# 2014 SRD 的职业等级数据在 Levels.json（Classes.json 的 class_levels 为空串）
levels = json.loads((SRC / "5e-SRD-Levels.json").read_text(encoding="utf-8"))
for lv in levels:
    if lv.get("level") in (1, 2) and lv.get("class", {}).get("index"):
        for f in lv.get("features", []):
            if isinstance(f, dict):
                names.add(f.get("name", ""))
            elif isinstance(f, str):
                names.add(f)

missing = sorted(n for n in names if n and n not in keys)
print(f"ZH 映射键: {len(keys)} | 界面将展示名称: {len(names)} | 缺失: {len(missing)}")
for n in missing:
    print(n)
print("--- 全部展示名称 ---")
for n in sorted(names):
    print(n)
