"""SQLite storage for conversations, messages, long-term memories, voice profiles and the security log.

Ownership (voice identification, 3.0): conversations and memories have an `owner` and user messages a `speaker`:
a voice profile's name, "misafir" (guest) or NULL (from before any voice was enrolled). Functions taking
`owner` use ALL ("*") to mean "no filter" (the mode before any voice is enrolled).
"""

import json
import sqlite3
from contextlib import contextmanager

from .config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS speakers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    embedding TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS security_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    event TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    score REAL
);
"""

ALL = "*"
# Columns added after the first version: (table, column, definition).
_NEW_COLUMNS = [
    ("conversations", "owner", "TEXT"),
    ("messages", "speaker", "TEXT"),
    ("memories", "owner", "TEXT"),
]


@contextmanager
def session():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with session() as conn:
        conn.executescript(SCHEMA)
        for table, column, definition in _NEW_COLUMNS:
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _owner_filter(owner: str) -> tuple[str, tuple]:
    return ("", ()) if owner == ALL else (" WHERE owner IS ?", (owner,))


# Conversations

def create_conversation(title: str, owner: str | None = None) -> int:
    with session() as conn:
        return conn.execute("INSERT INTO conversations (title, owner) VALUES (?, ?)", (title, owner)).lastrowid


def get_conversation(conversation_id: int):
    with session() as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        return dict(row) if row else None


def list_conversations(owner: str = ALL) -> list[dict]:
    where, args = _owner_filter(owner)
    with session() as conn:
        rows = conn.execute(f"SELECT * FROM conversations{where} ORDER BY updated_at DESC, id DESC", args).fetchall()
        return [dict(r) for r in rows]


def delete_conversation(conversation_id: int):
    with session() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


# Messages

def add_message(conversation_id: int, role: str, content: str, speaker: str | None = None):
    with session() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, speaker) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, speaker),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = datetime('now', 'localtime') WHERE id = ?",
            (conversation_id,),
        )


def list_messages(conversation_id: int) -> list[dict]:
    with session() as conn:
        rows = conn.execute(
            "SELECT id, role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def messages_after(message_id: int, limit: int) -> list[dict]:
    with session() as conn:
        rows = conn.execute(
            "SELECT id, role, content, speaker FROM messages WHERE id > ? ORDER BY id LIMIT ?",
            (message_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def last_message_id() -> int:
    with session() as conn:
        return conn.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0]


# Key-value state

def get_meta(key: str):
    with session() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None


def set_meta(key: str, value: str):
    with session() as conn:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


# Memories

def add_memory(content: str, owner: str | None = None) -> int:
    with session() as conn:
        return conn.execute("INSERT INTO memories (content, owner) VALUES (?, ?)", (content, owner)).lastrowid


def list_memories(owner: str = ALL) -> list[dict]:
    where, args = _owner_filter(owner)
    with session() as conn:
        rows = conn.execute(f"SELECT * FROM memories{where} ORDER BY id", args).fetchall()
        return [dict(r) for r in rows]


def get_memory(memory_id: int):
    with session() as conn:
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return dict(row) if row else None


def delete_memory(memory_id: int):
    with session() as conn:
        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))


# Voice profiles

def list_speakers() -> list[dict]:
    with session() as conn:
        rows = conn.execute("SELECT * FROM speakers ORDER BY id").fetchall()
    return [{**dict(r), "embedding": json.loads(r["embedding"]), "is_admin": bool(r["is_admin"])} for r in rows]


def count_speakers() -> int:
    with session() as conn:
        return conn.execute("SELECT COUNT(*) FROM speakers").fetchone()[0]


def save_speaker(name: str, embedding: list[float], is_admin: bool):
    """Add a voice profile, or replace the voice of an existing one (keeping its admin flag)."""
    with session() as conn:
        conn.execute(
            "INSERT INTO speakers (name, embedding, is_admin) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET embedding = excluded.embedding",
            (name, json.dumps(embedding), int(is_admin)),
        )


def delete_speaker(speaker_id: int):
    with session() as conn:
        conn.execute("DELETE FROM speakers WHERE id = ?", (speaker_id,))


def assign_unowned(owner: str):
    """When the first voice is enrolled, everything recorded before belongs to that person."""
    with session() as conn:
        conn.execute("UPDATE conversations SET owner = ? WHERE owner IS NULL", (owner,))
        conn.execute("UPDATE memories SET owner = ? WHERE owner IS NULL", (owner,))
        conn.execute("UPDATE messages SET speaker = ? WHERE speaker IS NULL AND role = 'user'", (owner,))


# Security log

def log_security(event: str, detail: str = "", score: float | None = None):
    with session() as conn:
        conn.execute("INSERT INTO security_log (event, detail, score) VALUES (?, ?, ?)", (event, detail, score))


def list_security_log(limit: int = 500) -> list[dict]:
    with session() as conn:
        rows = conn.execute("SELECT * FROM security_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
