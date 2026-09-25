"""SQLite storage for conversations, messages and long-term memories."""

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
"""


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


# Conversations

def create_conversation(title: str) -> int:
    with session() as conn:
        return conn.execute("INSERT INTO conversations (title) VALUES (?)", (title,)).lastrowid


def get_conversation(conversation_id: int):
    with session() as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        return dict(row) if row else None


def list_conversations() -> list[dict]:
    with session() as conn:
        rows = conn.execute("SELECT * FROM conversations ORDER BY updated_at DESC, id DESC").fetchall()
        return [dict(r) for r in rows]


def delete_conversation(conversation_id: int):
    with session() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


# Messages

def add_message(conversation_id: int, role: str, content: str):
    with session() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, role, content),
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


# Memories

def add_memory(content: str) -> int:
    with session() as conn:
        return conn.execute("INSERT INTO memories (content) VALUES (?)", (content,)).lastrowid


def list_memories() -> list[dict]:
    with session() as conn:
        rows = conn.execute("SELECT * FROM memories ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def delete_memory(memory_id: int):
    with session() as conn:
        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
