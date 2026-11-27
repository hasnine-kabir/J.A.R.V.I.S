import functools
import sqlite3
import threading
from datetime import datetime

from jarvis.core.brain import Message
from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.memory")


class ShortTermMemory:
    def __init__(self, max_messages: int = 50):
        self._messages: list[Message] = []
        self._max = max_messages

    def add(self, message: Message) -> None:
        self._messages.append(message)
        if len(self._messages) > self._max:
            self._messages = self._messages[-self._max:]

    def get_messages(self) -> list[Message]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()


class LongTermMemory:
    def __init__(self, db_path: str = "memory.db"):
        # Shared by the UI thread and worker threads; every method holds self._lock.
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS facts (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        self._conn.commit()

    def save_fact(self, key: str, value: str) -> None:
        now = datetime.now().isoformat()
        self._conn.execute(
            "INSERT INTO facts (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=?, updated_at=?",
            (key, value, now, value, now),
        )
        self._conn.commit()

    def get_facts(self) -> list[dict]:
        rows = self._conn.execute("SELECT key, value FROM facts ORDER BY updated_at DESC").fetchall()
        return [{"key": r["key"], "value": r["value"]} for r in rows]

    def save_note(self, content: str) -> None:
        now = datetime.now().isoformat()
        self._conn.execute("INSERT INTO notes (content, created_at) VALUES (?, ?)", (content, now))
        self._conn.commit()

    def get_notes(self) -> list[dict]:
        rows = self._conn.execute("SELECT id, content, created_at FROM notes ORDER BY created_at DESC").fetchall()
        return [{"id": r["id"], "content": r["content"], "created_at": r["created_at"]} for r in rows]

    def delete_note(self, note_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def delete_fact(self, key: str) -> bool:
        cur = self._conn.execute("DELETE FROM facts WHERE key = ?", (key,))
        self._conn.commit()
        return cur.rowcount > 0

    def save_session_summary(self, summary: str) -> None:
        now = datetime.now().isoformat()
        self._conn.execute("INSERT INTO history (summary, created_at) VALUES (?, ?)", (summary, now))
        self._conn.commit()

    def get_last_session_summary(self) -> str | None:
        row = self._conn.execute("SELECT summary FROM history ORDER BY created_at DESC LIMIT 1").fetchone()
        return row["summary"] if row else None

    def search(self, query: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT 'note' as type, content, created_at FROM notes WHERE content LIKE ? "
            "UNION ALL "
            "SELECT 'fact' as type, key || ': ' || value as content, updated_at as created_at FROM facts WHERE key LIKE ? OR value LIKE ? "
            "ORDER BY created_at DESC",
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        ).fetchall()
        return [{"type": r["type"], "content": r["content"]} for r in rows]

    def close(self) -> None:
        self._conn.close()


def _locked(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


for _name, _fn in list(vars(LongTermMemory).items()):
    if callable(_fn) and not _name.startswith("__"):
        setattr(LongTermMemory, _name, _locked(_fn))
