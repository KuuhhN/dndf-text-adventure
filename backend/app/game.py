"""游戏会话持久化：角色卡 + 对话历史（SQLite）。"""
import json
import os
import sqlite3
import uuid

DB_PATH = os.environ.get(
    "DNDF_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "dndf.db"),
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                name TEXT,
                character TEXT,
                history TEXT DEFAULT '[]',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )"""
        )


def create_session(name: str, character: dict) -> str:
    init_db()
    sid = uuid.uuid4().hex[:12]
    with _conn() as c:
        c.execute(
            "INSERT INTO sessions (id, name, character) VALUES (?, ?, ?)",
            (sid, name, json.dumps(character, ensure_ascii=False)),
        )
    return sid


def get_session(sid: str) -> dict | None:
    init_db()
    with _conn() as c:
        row = c.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "character": json.loads(row["character"]),
        "history": json.loads(row["history"]),
    }


def update_character(sid: str, character: dict):
    with _conn() as c:
        c.execute(
            "UPDATE sessions SET character = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(character, ensure_ascii=False), sid),
        )


def append_history(sid: str, role: str, content: str):
    s = get_session(sid)
    history = s["history"] if s else []
    history.append({"role": role, "content": content})
    with _conn() as c:
        c.execute(
            "UPDATE sessions SET history = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(history, ensure_ascii=False), sid),
        )


def list_sessions() -> list[dict]:
    init_db()
    with _conn() as c:
        rows = c.execute("SELECT id, name, created_at, updated_at FROM sessions ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]
