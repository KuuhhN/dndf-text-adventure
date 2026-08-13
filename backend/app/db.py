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
def list_spells(level: int | None = None) -> list[str]:
    with _conn() as c:
        if level is None:
            rows = c.execute('SELECT name FROM spells ORDER BY level, name').fetchall()
        else:
            rows = c.execute('SELECT name FROM spells WHERE level = ? ORDER BY name', (level,)).fetchall()
    return [r["name"] for r in rows]
