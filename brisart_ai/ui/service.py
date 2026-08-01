"""GUI-facing service layer for BrisartAI.

Widgets in ui/ never touch Index, SessionMemory, or ResearchSettings
directly. Everything routes through BrisartService so the desktop UI
and any future interface share the exact same backend logic (ingestion,
search, settings, notes, etc.) instead of duplicating it.

Notes are stored through knowledge/vault.py's add_note()/list_notes()/
search_notes() helpers. Notes live in the vault's own notes table and
are surfaced with list_notes()/search_notes(); they are separate from
the file/web source index used by the main ask() pipeline. Collections,
entity extraction, and timeline features from vault.py are intentionally
not wired in here to keep the surface area small.
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
from brisart_ai.knowledge.vault import add_note, list_notes, search_notes
from brisart_ai.web.crawler import web_search_and_ingest

# Diagnostic lines are only worth surfacing to the user if they contain
# one of these markers -- the rest of the crawl/search log (per-URL
# fetch lines, "OK: N chars" progress, etc.) is normal verbose noise
# that belongs in the console, not the chat transcript.
_DIAGNOSTIC_MARKERS = ("WARN", "SKIP", "ERROR")
_MAX_DIAGNOSTIC_LINES = 5


class BrisartService:
    """Owns one Index, SessionMemory, and ResearchSettings for the app's lifetime."""

    def __init__(self, db_path: str = DEFAULT_DB):
        self.db_path = db_path
        self.index = Index(db_path)
        # Remove any stale dictionary/definition web pages left in the
        # database by earlier builds so they cannot resurface in answers.
        removed = self.index.purge_blocked_web_sources()
        if removed:
            print(
                f"Startup cleanup: removed {removed} stale "
                "dictionary/definition page(s) from the index."
            )
        self.memory = SessionMemory(db_path)
        self.settings = ResearchSettings()
        # Guards stdout redirection below -- only one ask() should be
        # capturing print() output at a time. The app's _busy flag
        # already prevents overlapping requests from the UI, but this
        # lock keeps the service safe even if called from elsewhere.
        self._stdout_lock = threading.Lock()
        self.last_diagnostics: List[str] = []

    # -- status ---------------------------------------------------------
    def counts(self) -> Tuple[int, int, int]:
        total = self.index.source_count()
        files = self.index.source_count("file")
        web = self.index.source_count("web")
        return total, files, web

    # -- conversation -----------------------------------------------------
    def ask(
        self,
        text: str,
        limit: int = 8,
        web_limit: int = 5,
        force_web: Optional[bool] = None,
    ) -> str:
        """Answer a question.

        When ``force_web`` is left as ``None`` (the default for typed
        chat questions), the decision to search the public web is taken
        from the "Automatic Web Research" setting, so the settings
        toggle actually has an effect again. Callers that want to
        guarantee a fresh web search regardless of the setting -- such
        as the explicit "Research Web" sidebar action -- should pass
        ``force_web=True``.

        Diagnostic output printed by the crawler/search/policy/fetcher
        layers during this call is captured rather than left console-
        only; the interesting lines (WARN/SKIP/ERROR) are available
        afterward via ``last_diagnostics``.
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
        """Pull out only the WARN/SKIP/ERROR lines worth showing the user."""
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

    # -- ingestion --------------------------------------------------------
    def import_paths(self, paths: List[str]) -> str:
        count = ingest_paths(paths, self.index)
        total, _files, _web = self.counts()
        return f"Ingested {count} file(s) this run. Indexed sources total: {total}"

    # -- research ---------------------------------------------------------
    def research(self, query: str, limit: int = 5, depth: int = 0) -> str:
        count = web_search_and_ingest(query, self.index, limit=limit, crawl_depth=depth)
        total, _files, _web = self.counts()
        return f"Web pages indexed this run: {count}. Indexed sources total: {total}"

    # -- notes ------------------------------------------------------------
    def add_note(self, title: str, body: str) -> str:
        return add_note(self.index, title, body)

    def list_notes(self, limit: int = 20) -> str:
        return list_notes(self.index, limit=limit)

    def search_notes(self, query: str, limit: int = 10) -> str:
        return search_notes(self.index, query, limit=limit)

    # -- settings ---------------------------------------------------------------
    def toggle_setting(self, key: str) -> Tuple[str, bool]:
        resolved = self.settings.resolve_key(key)
        new_value = self.settings.toggle(resolved)
        return TOGGLE_LABELS.get(resolved, resolved), new_value

    def settings_panel_text(self) -> str:
        return self.settings.render()

    # -- lifecycle --------------------------------------------------------------
    def close(self) -> None:
        self.memory.close()
        self.index.close()


__all__ = ["BrisartService"]
