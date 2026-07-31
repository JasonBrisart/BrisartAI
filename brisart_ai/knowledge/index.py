"""SQLite knowledge index for BrisartAI."""

from __future__ import annotations

import collections
import re
import sqlite3
import urllib.parse
from pathlib import Path
from typing import Optional

from brisart_ai.util import now_ts, stable_hash, tokenize


# Anchor the database to the project root (the folder that contains the
# brisart_ai package) so it is always created in the same, easy-to-find
# place -- right next to brisartai.py -- no matter which directory you
# launch BrisartAI from. Previously this was a bare relative filename, so
# the database was silently created in the terminal's current working
# directory (e.g. VS Code's install folder), which is exactly why it
# looked like it "did not exist" in the project folder and why stale rows
# kept surviving deletions.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = str(_PROJECT_ROOT / "brisart_ai_index.sqlite3")


# Dictionary / thesaurus / definition sites. Web sources from these hosts
# are almost never the answer to a factual research question. Any such
# rows left over in an existing database from earlier runs are purged
# automatically on startup by ``purge_junk_web_sources()``.
_BLOCKED_WEB_HOSTS = (
    "merriam-webster.com",
    "dictionary.cambridge.org",
    "dictionary.com",
    "thesaurus.com",
    "collinsdictionary.com",
    "vocabulary.com",
    "wordnik.com",
    "yourdictionary.com",
    "definitions.net",
    "wordreference.com",
    "urbandictionary.com",
    "ldoceonline.com",
    "macmillandictionary.com",
    "usdictionary.com",
    "en.wiktionary.org",
    "wiktionary.org",
    "britannica.com",
    "wordhippo.com",
    "powerthesaurus.org",
)


# Bare function / question words. A Wikipedia page whose title is exactly
# one of these (e.g. /wiki/Many) is a disambiguation page about the WORD,
# not a topic answer, and is purged from the index on startup.
_FUNCTION_WORDS = {
    "a", "about", "an", "and", "are", "as", "at", "be", "by", "can",
    "could", "did", "do", "does", "for", "from", "get", "give", "how",
    "i", "in", "into", "is", "it", "its", "list", "many", "me", "much",
    "of", "on", "or", "over", "please", "should", "show", "some", "tell",
    "that", "the", "their", "them", "then", "there", "these", "they",
    "this", "those", "to", "under", "us", "want", "was", "we", "were",
    "what", "when", "where", "which", "who", "whom", "why", "will",
    "with", "would", "you", "your",
}

_WIKI_TITLE = re.compile(r"/wiki/([^/#?]+)")


def _host_is_blocked(location: str) -> bool:
    """Return True when an indexed web location is a blocked host."""
    try:
        host = urllib.parse.urlsplit(str(location or "")).hostname or ""
    except ValueError:
        return False
    host = host.casefold().strip(".")
    if not host:
        return False
    return any(
        host == blocked or host.endswith("." + blocked)
        for blocked in _BLOCKED_WEB_HOSTS
    )


def _is_offtopic_wiki(location: str) -> bool:
    """Return True for a Wikipedia page about a bare function word."""
    try:
        parsed = urllib.parse.urlsplit(str(location or ""))
    except ValueError:
        return False
    if "wikipedia.org" not in (parsed.hostname or "").casefold():
        return False
    match = _WIKI_TITLE.search(parsed.path)
    if not match:
        return False
    title = (
        urllib.parse.unquote(match.group(1))
        .replace("_", " ")
        .strip()
        .casefold()
    )
    return title in _FUNCTION_WORDS


def _is_junk_web_source(location: str) -> bool:
    """Combined check: blocked dictionary host or off-topic wiki page."""
    return _host_is_blocked(location) or _is_offtopic_wiki(location)


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

    def purge_junk_web_sources(self) -> int:
        """Delete stale dictionary and off-topic web rows from the index.

        Older BrisartAI builds indexed dictionary "definition card" pages
        (e.g. results for the word "many") and Wikipedia disambiguation
        pages for bare words (e.g. /wiki/Many) before those were filtered.
        Those rows persist in the SQLite file across restarts and can
        still surface in answers. This removes them -- and their term rows
        -- so old junk cannot resurface, without touching local files or
        legitimate web pages. Returns the number of rows removed.
        """
        try:
            rows = self.conn.execute(
                """
                SELECT id, location
                FROM sources
                WHERE source_type = 'web'
                """
            ).fetchall()
        except sqlite3.Error:
            return 0

        doomed = [
            int(source_id)
            for source_id, location in rows
            if _is_junk_web_source(location)
        ]

        if not doomed:
            return 0

        with self.conn:
            self.conn.executemany(
                "DELETE FROM terms WHERE source_id = ?",
                [(source_id,) for source_id in doomed],
            )
            self.conn.executemany(
                "DELETE FROM sources WHERE id = ?",
                [(source_id,) for source_id in doomed],
            )

        return len(doomed)

    # Backwards-compatible alias for the previous method name.
    def purge_blocked_web_sources(self) -> int:
        return self.purge_junk_web_sources()

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
