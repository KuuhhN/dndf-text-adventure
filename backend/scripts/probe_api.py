# -*- coding: utf-8 -*-
"""检查运行中 /api/classes/{name} 返回的 level_features 字段（是否含 summary）。"""
import json
import sys
import urllib.request

name = sys.argv[1] if len(sys.argv) > 1 else "Fighter"
with urllib.request.urlopen(f"http://127.0.0.1:8000/api/classes/{name}", timeout=10) as resp:
    d = json.load(resp)
lf = d.get("level_features", {})
print("级别:", sorted(lf.keys()))
feat = lf.get("1", [{}])[0]
print("特性字段:", list(feat.keys()))
print("summary:", (feat.get("summary") or "")[:50])
print("desc 前 50 字:", (feat.get("desc") or "")[:50])
