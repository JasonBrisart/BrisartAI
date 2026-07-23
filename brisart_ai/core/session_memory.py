"""Tiny local session memory for BrisartAI.

Stores compact recent user topics instead of huge assistant outputs or raw
shell commands.
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
        self.conn = sqlite3.connect(db_path)
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

        if role == "assistant":
            if "What I do:" in content:
                return "assistant capabilities and self-description"
            if "Recommendations:" in content:
                return "recommendations from indexed data"
            if "Index summary:" in content:
                return "index analysis"
            if "Answer:" in content:
                after = content.split("Answer:", 1)[1].strip()
                return after[:140]

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