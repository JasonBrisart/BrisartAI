"""brisart_ai/ui/service.py

The backend facade every UI widget goes through instead of touching
`Index`/`SessionMemory`/`ResearchSettings` directly, so ingestion,
search, settings, and notes have exactly one implementation shared by
the desktop UI (and any future interface).

Construction order matters: `Index`/`SessionMemory` are built with NO
try/except around them, deliberately. A locked, read-only, or otherwise
unopenable database must propagate straight out of `__init__` uncaught,
so `ui/app.py`'s `run()` can catch it in exactly one place and show a
friendly dialog instead of a raw traceback. Two cleanup passes run at
startup as a side effect of construction: stale dictionary/definition
web pages get purged, and any notes saved before note-mirroring existed
get reindexed for ranked search -- both print a summary line only when
they actually did something, so a clean startup stays quiet.

`ask()` is the one method `ui/app.py`'s background worker thread calls.
When `force_web=None` (ordinary typed questions), the web-search
decision is deferred to the `auto_web_research` setting; the explicit
"Research Web" action passes `force_web=True` to force a fresh search
regardless. Diagnostic print() output from the crawler/search/policy
layers during a call is captured (via `contextlib.redirect_stdout`) and
filtered down to just the WARN/SKIP/ERROR lines worth surfacing in the
chat transcript, available afterward as `last_diagnostics`.

Notes route through `knowledge/vault.py`'s helpers; collections, entity
extraction, and timeline features from vault.py are intentionally not
wired in here to keep the UI's surface small.
"""
from __future__ import annotations

import contextlib
import io
import threading
from typing import List, Optional, Tuple

from brisart_ai.core.conversation import build_conversation_answer
from brisart_ai.core.session_memory import SessionMemory
from brisart_ai.core.settings import ResearchSettings, TOGGLE_LABELS
from brisart_ai.knowledge.index import DEFAULT_DB, Index
from brisart_ai.knowledge.ingest import ingest_paths
from brisart_ai.knowledge.vault import (
    add_note,
    list_notes,
    reindex_missing_notes,
    search_notes,
)
from brisart_ai.web.crawler import web_search_and_ingest

# Only these markers are worth surfacing to the user; everything else
# printed during a search/crawl is normal verbose progress output.
_DIAGNOSTIC_MARKERS = ("WARN", "SKIP", "ERROR")
_MAX_DIAGNOSTIC_LINES = 5


class BrisartService:
    """Owns one Index, SessionMemory, and ResearchSettings for the app's lifetime."""

    def __init__(self, db_path: str = DEFAULT_DB):
        self.db_path = db_path
        # Deliberately unguarded -- see module docstring.
        self.index = Index(db_path)

        removed = self.index.purge_blocked_web_sources()
        if removed:
            print(
                f"Startup cleanup: removed {removed} stale "
                "dictionary/definition page(s) from the index."
            )

        reindexed = reindex_missing_notes(self.index)
        if reindexed:
            print(
                f"Startup cleanup: indexed {reindexed} previously "
                "unindexed note(s) for ranked search."
            )

        self.memory = SessionMemory(db_path)
        self.settings = ResearchSettings()

        # Guards stdout redirection in ask(); the app's _busy flag
        # already prevents overlapping requests from the UI, but this
        # keeps the service itself safe if called from elsewhere too.
        self._stdout_lock = threading.Lock()
        self.last_diagnostics: List[str] = []

    def counts(self) -> Tuple[int, int, int]:
        total = self.index.source_count()
        files = self.index.source_count("file")
        web = self.index.source_count("web")
        return total, files, web

    def ask(
        self,
        text: str,
        limit: int = 8,
        web_limit: int = 5,
        force_web: Optional[bool] = None,
    ) -> str:
        """Answer a question.

        `force_web=None` defers the web-search decision to the
        Automatic Web Research setting; pass `force_web=True` to
        guarantee a fresh web search regardless (the "Research Web"
        action).
        """
        resolved_force_web = (
            self.settings.get("auto_web_research")
            if force_web is None
            else bool(force_web)
        )

        buffer = io.StringIO()
        with self._stdout_lock:
            with contextlib.redirect_stdout(buffer):
                answer = build_conversation_answer(
                    text,
                    self.index,
                    self.memory,
                    limit=limit,
                    settings=self.settings,
                    web_limit=web_limit,
                    force_web=resolved_force_web,
                )
        self.last_diagnostics = self._extract_diagnostics(buffer.getvalue())
        return answer

    @staticmethod
    def _extract_diagnostics(captured_output: str) -> List[str]:
        """Pull out just the WARN/SKIP/ERROR lines worth showing the user."""
        highlights: List[str] = []
        seen = set()
        for line in captured_output.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            if not any(marker in cleaned for marker in _DIAGNOSTIC_MARKERS):
                continue
            if cleaned in seen:
                continue
            seen.add(cleaned)
            highlights.append(cleaned)
            if len(highlights) >= _MAX_DIAGNOSTIC_LINES:
                break
        return highlights

    def import_paths(self, paths: List[str]) -> str:
        count = ingest_paths(paths, self.index)
        total, _files, _web = self.counts()
        return f"Ingested {count} file(s) this run. Indexed sources total: {total}"

    def research(self, query: str, limit: int = 5, depth: int = 0) -> str:
        count = web_search_and_ingest(query, self.index, limit=limit, crawl_depth=depth)
        total, _files, _web = self.counts()
        return f"Web pages indexed this run: {count}. Indexed sources total: {total}"

    def add_note(self, title: str, body: str) -> str:
        return add_note(self.index, title, body)

    def list_notes(self, limit: int = 20) -> str:
        return list_notes(self.index, limit=limit)

    def search_notes(self, query: str, limit: int = 10) -> str:
        return search_notes(self.index, query, limit=limit)

    def toggle_setting(self, key: str) -> Tuple[str, bool]:
        resolved = self.settings.resolve_key(key)
        new_value = self.settings.toggle(resolved)
        return TOGGLE_LABELS.get(resolved, resolved), new_value

    def settings_panel_text(self) -> str:
        return self.settings.render()

    def close(self) -> None:
        self.memory.close()
        self.index.close()


__all__ = ["BrisartService"]
