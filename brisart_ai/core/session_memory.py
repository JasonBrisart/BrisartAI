"""
File: brisart_ai/core/session_memory.py

Purpose
-------
A tiny SQLite-backed rolling log of recent chat topics.

Communication / relationships
------------------------------
- brisart_ai/core/conversation.py: recent_topics() / add().
- brisart_ai/ui/service.py: constructs the single SessionMemory instance.
- Imports brisart_ai.io.input_cleaner.normalize_shellish_input() and
  brisart_ai.util.now_ts()/tokenize().

Settings / parameters
----------------------
- check_same_thread=False.
- _compress(): tokenizes, caps at 12 terms, falls back to 140 chars.
- recent_topics(limit=6).

Edge cases
----------
- add() drops rows that compress to nothing.
- Content capped at 400 chars at the SQL layer.

Known limitations
-----------------
- Stores a compressed token summary of each turn, not full text, so
  exact wording is not recoverable from memory.
- recent_topics() is a simple recency de-dupe, not semantic clustering;
  near-duplicate phrasings can both appear.
- Single-file SQLite with no cross-process locking guarantees beyond
  SQLite's own WAL mode.

Examples
--------
    >>> mem = SessionMemory(":memory:")
    >>> mem.add("user", "who founded microsoft")
    >>> mem.recent_topics(limit=4)
    ['who founded microsoft']
"""
from __future__ import annotations

import re
import sqlite3
from typing import List

from brisart_ai.io.input_cleaner import normalize_shellish_input
from brisart_ai.util import now_ts, tokenize


class SessionMemory:
    """SQLite-backed compact session memory."""

    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        self.conn.commit()

    def _compress(self, role: str, content: str) -> str:
        content = normalize_shellish_input(content.strip())
        content = re.sub(r"\s+", " ", content)
        terms = tokenize(content)
        if terms:
            return " ".join(terms[:12])
        return content[:140]

    def add(self, role: str, content: str) -> None:
        compact = self._compress(role, content)
        if not compact:
            return
        with self.conn:
            self.conn.execute(
                "INSERT INTO conversation_memory(role, content, created_at) VALUES(?,?,?)",
                (role, compact[:400], now_ts()),
            )

    def recent_topics(self, limit: int = 6) -> List[str]:
        rows = self.conn.execute(
            "SELECT content FROM conversation_memory ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        topics = []
        seen = set()
        for (content,) in rows:
            clipped = " ".join(content.split())[:120]
            if clipped and clipped not in seen:
                seen.add(clipped)
                topics.append(clipped)
        return topics

    def close(self) -> None:
        self.conn.close()



