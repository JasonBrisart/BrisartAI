"""SQLite knowledge index for BrisartAI."""

from __future__ import annotations

import collections
import sqlite3
from typing import Optional

from brisart_ai.util import now_ts, stable_hash, tokenize


DEFAULT_DB = "brisart_ai_index.sqlite3"


class Index:
    """Local SQLite-backed source and term index."""

    def __init__(self, path: str = DEFAULT_DB):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)

        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

        self._init_schema()

    def _init_schema(self) -> None:
        """Create the core index schema when needed."""

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
                FOREIGN KEY(source_id)
                    REFERENCES sources(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_terms_term
                ON terms(term);

            CREATE INDEX IF NOT EXISTS idx_sources_type
                ON sources(source_type);

            CREATE INDEX IF NOT EXISTS idx_sources_location
                ON sources(location);

            CREATE INDEX IF NOT EXISTS idx_sources_indexed_at
                ON sources(indexed_at);
            """
        )

        self.conn.commit()

    def add_source(
        self,
        source_type: str,
        location: str,
        title: str,
        text: str,
        content_hash: str = "",
        size_bytes: int = 0,
        extension: str = "",
    ) -> bool:
        """Add or update an indexed source.

        Returns True when non-empty text was indexed.
        """

        cleaned_type = str(source_type or "").strip()
        cleaned_location = str(location or "").strip()
        cleaned_title = str(title or "").strip()
        cleaned_text = str(text or "").strip()
        cleaned_hash = str(content_hash or "").strip()
        cleaned_extension = str(extension or "").strip().lower()

        if not cleaned_type:
            raise ValueError("source_type cannot be empty")

        if not cleaned_location:
            raise ValueError("location cannot be empty")

        if not cleaned_text:
            return False

        source_key = stable_hash(
            cleaned_type + "|" + cleaned_location
        )

        indexed_at = now_ts()

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sources(
                    source_key,
                    source_type,
                    location,
                    title,
                    text,
                    content_hash,
                    size_bytes,
                    extension,
                    indexed_at
                )
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source_key) DO UPDATE SET
                    source_type = excluded.source_type,
                    location = excluded.location,
                    title = excluded.title,
                    text = excluded.text,
                    content_hash = excluded.content_hash,
                    size_bytes = excluded.size_bytes,
                    extension = excluded.extension,
                    indexed_at = excluded.indexed_at
                """,
                (
                    source_key,
                    cleaned_type,
                    cleaned_location,
                    cleaned_title,
                    cleaned_text,
                    cleaned_hash,
                    max(0, int(size_bytes or 0)),
                    cleaned_extension,
                    indexed_at,
                ),
            )

            row = self.conn.execute(
                """
                SELECT id
                FROM sources
                WHERE source_key = ?
                """,
                (source_key,),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "Source was written but could not be retrieved"
                )

            source_id = int(row[0])

            self.conn.execute(
                """
                DELETE FROM terms
                WHERE source_id = ?
                """,
                (source_id,),
            )

            counts = collections.Counter(
                tokenize(
                    cleaned_title
                    + " "
                    + cleaned_location
                    + " "
                    + cleaned_text
                )
            )

            if counts:
                self.conn.executemany(
                    """
                    INSERT OR REPLACE INTO terms(
                        term,
                        source_id,
                        tf
                    )
                    VALUES(?,?,?)
                    """,
                    [
                        (
                            term,
                            source_id,
                            int(term_frequency),
                        )
                        for term, term_frequency
                        in counts.items()
                    ],
                )

        return True

    def source_count(
        self,
        source_type: Optional[str] = None,
    ) -> int:
        """Return the total number of indexed sources."""

        if source_type:
            row = self.conn.execute(
                """
                SELECT COUNT(*)
                FROM sources
                WHERE source_type = ?
                """,
                (source_type,),
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT COUNT(*)
                FROM sources
                """
            ).fetchone()

        return int(row[0] if row else 0)

    def clear(self) -> None:
        """Remove all indexed sources and terms."""

        with self.conn:
            self.conn.execute("DELETE FROM terms")
            self.conn.execute("DELETE FROM sources")

    def close(self) -> None:
        """Close the SQLite connection."""

        self.conn.close()

    def __enter__(self) -> "Index":
        return self

    def __exit__(
        self,
        exception_type,
        exception_value,
        traceback,
    ) -> None:
        self.close()


__all__ = [
    "DEFAULT_DB",
    "Index",
]