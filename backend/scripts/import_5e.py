"""导入 5e-database（src/2014/en/*.json）到 SQLite。

用法：python scripts/import_5e.py
数据源：data/5e-database（clone 自 https://github.com/5e-bits/5e-database，MIT + OGL）
输出：data/dndf.db（幂等：每次重建）
"""
import json
import os
import sqlite3
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BACKEND_DIR, "data", "5e-database", "src", "2014", "en")
DB_PATH = os.path.join(BACKEND_DIR, "data", "dndf.db")

# 表名 -> (文件名前缀, 需要冗余提取的字段)
TABLES = {
    "races": ("5e-SRD-Races", ["name", "size", "speed"]),
    "classes": ("5e-SRD-Classes", ["name", "hit_die"]),
    "subclasses": ("5e-SRD-Subclasses", ["name"]),
    "spells": ("5e-SRD-Spells", ["name", "level", "school"]),
    "monsters": ("5e-SRD-Monsters", ["name", "hit_points", "challenge_rating", "xp"]),
    "equipment": ("5e-SRD-Equipment", ["name", "equipment_category"]),
    "features": ("5e-SRD-Features", ["name", "level"]),
    "ability_scores": ("5e-SRD-Ability-Scores", ["name", "full_name"]),
    "skills": ("5e-SRD-Skills", ["name"]),
    "backgrounds": ("5e-SRD-Backgrounds", ["name"]),
    "languages": ("5e-SRD-Languages", ["name"]),
    "proficiencies": ("5e-SRD-Proficiencies", ["name"]),
}


def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    total = 0
    for table, (prefix, fields) in TABLES.items():
        path = os.path.join(SRC_DIR, f"{prefix}.json")
        if not os.path.exists(path):
            print(f"  跳过 {table}（{os.path.basename(path)} 不存在）")
            continue
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
        cur.execute(f"DROP TABLE IF EXISTS {table}")
        cols = ["id INTEGER PRIMARY KEY", "name TEXT", "data TEXT"]
        for field in fields[1:]:  # name 已含
            cols.append(f'"{field}" TEXT')
        cur.execute(f"CREATE TABLE {table} ({', '.join(cols)})")
        for i, item in enumerate(items):
            name = item.get("name", "")
            data = json.dumps(item, ensure_ascii=False)
            extra = [json.dumps(item.get(f), ensure_ascii=False) if isinstance(item.get(f), (dict, list)) else item.get(f)
                     for f in fields[1:]]
            cur.execute(
                f"INSERT INTO {table} (id, name, data{', ' + ', '.join('"' + f + '"' for f in fields[1:]) if fields[1:] else ''}) "
                f"VALUES (?, ?, ?{', ?' * len(fields[1:])})",
                [i, name, data] + extra,
            )
        total += len(items)
        print(f"  {table}: {len(items)} 条")
    conn.commit()
    conn.close()
    print(f"完成，共导入 {total} 条 -> {DB_PATH}")


if __name__ == "__main__":
    sys.exit(main())
