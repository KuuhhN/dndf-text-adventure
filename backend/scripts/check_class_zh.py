# -*- coding: utf-8 -*-
"""收集职业详情 API 返回的英文字段（proficiencies/豁免/技能/特性名），对照前端 ZH 找缺失。"""
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from app import db  # noqa: E402

# 前端 ZH 键
jsx = (BASE.parent / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
zh_block = re.search(r"const ZH = \{.*?\};", jsx, re.S).group(0)
keys = set()
for m in re.finditer(r"(?:^\s*|,)\s*[\"\']?([A-Za-z][A-Za-z0-9 _\'\"]*?)[\"\']?\s*:", zh_block, re.M):
    k = m.group(1).strip('"\'')
    if k and not k.startswith("//"):
        keys.add(k)

english = {}  # field -> set(names)
for cls in db.list_classes():
    d = db.get_class_detail(cls)
    for p in d.get("proficiencies", []):
        english.setdefault("proficiencies", set()).add(p)
    for st in d.get("saving_throws", []):
        english.setdefault("saving_throws", set()).add(st)
    for sk in d.get("skill_choices", {}).get("options", []):
        english.setdefault("skill_choices", set()).add(sk)
    for lv, feats in d.get("level_features", {}).items():
        for f in feats:
            english.setdefault("level_features", set()).add(f.get("name", ""))

print("=== 职业详情中无 ZH 映射的英文 ===")
for field, names in sorted(english.items()):
    missing = sorted(n for n in names if n not in keys)
    print(f"\n[{field}] {len(names)} 个，缺失 {len(missing)} 个:")
    for m in missing:
        print("  ", m)
