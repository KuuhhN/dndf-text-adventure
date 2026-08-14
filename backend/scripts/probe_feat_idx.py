# -*- coding: utf-8 -*-
"""探针：levels.json 的 features 引用 vs features 表 data 的 index 是否一致。"""
import json
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "data" / "5e-database" / "src" / "2014" / "en"

levels = json.loads((SRC / "5e-SRD-Levels.json").read_text(encoding="utf-8"))
conn = sqlite3.connect(BASE / "data" / "dndf.db")
conn.row_factory = sqlite3.Row

feat_indices = {
    r["idx"]
    for r in conn.execute("SELECT json_extract(data, '$.index') AS idx FROM features")
}
trait_indices = {
    r["idx"]
    for r in conn.execute("SELECT json_extract(data, '$.index') AS idx FROM traits")
}

for lv in levels:
    if lv.get("level") == 1 and lv.get("class", {}).get("index") == "fighter":
        print("Fighter Lv1 引用:")
        for f in lv.get("features", []):
            print("  ", f)
        break

print("\nfeatures 表 index 示例:", sorted(feat_indices)[:10])
print("traits 表 index 示例:", sorted(trait_indices)[:10])

# 引用 index 是否存在
ref = set()
for lv in levels:
    for f in lv.get("features", []):
        ref.add(f.get("index", ""))
print("\n引用总数:", len(ref), "| 在 features 表:", len(ref & feat_indices),
      "| 在 traits 表:", len(ref & trait_indices), "| 都不在:", len(ref - feat_indices - trait_indices))
print("都不在的示例:", sorted(ref - feat_indices - trait_indices)[:8])
