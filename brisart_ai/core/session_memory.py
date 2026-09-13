"""
File: brisart_ai/core/session_memory.py

Purpose
-------
A tiny SQLite-backed rolling log of recent chat topics -- not full
answers, just compressed keywords -- so core/conversation.py can hand
knowledge/synthesizer.py a bit of "what has this chat been about"
context. Shares its SQLite file with knowledge/index.py's Index but
owns a separate conversation_memory table.

Communication / relationships
------------------------------
- brisart_ai/core/conversation.py: calls .recent_topics() before
  answering and .add() after, for both the user's question and the
  assistant's answer.
- brisart_ai/ui/service.py: constructs the single SessionMemory instance
  for the app's lifetime, sharing db_path with the main Index.
- Imports brisart_ai.io.input_cleaner.normalize_shellish_input() and
  brisart_ai.util.now_ts()/tokenize().

Settings / parameters
----------------------
- check_same_thread=False: required because web research runs on a
  background thread (ui/app.py) while this connection is created on the
  main thread; the app already serializes requests via
  BrisartApp._busy, so no extra locking was needed.
- _compress(): tokenizes content and caps it at 12 terms, falling back
  to the first 140 raw characters only if tokenization finds nothing
  (e.g. an all-stopword or all-punctuation message).
- recent_topics(limit=6): returns the most-recent, de-duplicated topics
  newest-first, each clipped to 120 characters for display.

Edge cases
----------
- add() silently drops a row that compresses to nothing (e.g. an
  all-whitespace message) rather than storing an empty topic.
- Stored content is also hard-capped at 400 characters at the SQL layer
  as a second safety net beyond the 12-term/140-character compression.
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
                """
                INSERT INTO conversation_memory(role, content, created_at)
                VALUES(?,?,?)
                """,
                (role, compact[:400], now_ts()),
            )

    def recent_topics(self, limit: int = 6) -> List[str]:
        """Most-recent, de-duplicated topics, newest first."""
        rows = self.conn.execute(
            """
            SELECT content
            FROM conversation_memory
            ORDER BY created_at DESC
            LIMIT ?
            """,
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
