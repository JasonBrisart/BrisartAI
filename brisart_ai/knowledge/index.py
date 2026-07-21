"""SQLite index for local files and optional web pages."""

from __future__ import annotations

import collections
import sqlite3
from typing import Optional

from .util import now_ts, stable_hash, tokenize

DEFAULT_DB = "brisart_ai_index.sqlite3"


class Index:
    def __init__(self, path: str = DEFAULT_DB):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_key TEXT UNIQUE NOT NULL,
                source_type TEXT NOT NULL,
                location TEXT NOT NULL,
                title TEXT,
                text TEXT NOT NULL,
                content_hash TEXT,
                size_bytes INTEGER,
                extension TEXT,
                indexed_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS terms (
                term TEXT NOT NULL,
                source_id INTEGER NOT NULL,
                tf INTEGER NOT NULL,
                PRIMARY KEY(term, source_id),
                FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_terms_term ON terms(term);
            CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(source_type);
            CREATE INDEX IF NOT EXISTS idx_sources_location ON sources(location);
            """
        )
        self.conn.commit()

    def add_source(self, source_type: str, location: str, title: str, text: str, content_hash: str = "", size_bytes: int = 0, extension: str = "") -> None:
        if not text.strip():
            return
        source_key = stable_hash(source_type + "|" + location)
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sources(source_key, source_type, location, title, text, content_hash, size_bytes, extension, indexed_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source_key) DO UPDATE SET
                    title=excluded.title,
                    text=excluded.text,
                    content_hash=excluded.content_hash,
                    size_bytes=excluded.size_bytes,
                    extension=excluded.extension,
                    indexed_at=excluded.indexed_at
                """,
                (source_key, source_type, location, title, text, content_hash, size_bytes, extension, now_ts()),
            )
            source_id = self.conn.execute("SELECT id FROM sources WHERE source_key=?", (source_key,)).fetchone()[0]
            self.conn.execute("DELETE FROM terms WHERE source_id=?", (source_id,))
            counts = collections.Counter(tokenize((title or "") + " " + text))
            self.conn.executemany(
                "INSERT OR REPLACE INTO terms(term, source_id, tf) VALUES(?,?,?)",
                [(term, source_id, tf) for term, tf in counts.items()],
            )

    def source_count(self, source_type: Optional[str] = None) -> int:
        if source_type:
            return int(self.conn.execute("SELECT COUNT(*) FROM sources WHERE source_type=?", (source_type,)).fetchone()[0])
        return int(self.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0])

    def close(self) -> None:
        self.conn.close()
