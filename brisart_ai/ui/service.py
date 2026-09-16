"""
File: brisart_ai/ui/service.py

Purpose
-------
The backend facade every UI widget goes through instead of touching
Index/SessionMemory/ResearchSettings directly. It owns the single
session RelevanceFeedback store, so relevance feedback is a standard part
of every ranked search for the app's lifetime.

Communication / relationships
------------------------------
- brisart_ai/ui/app.py: constructs the single BrisartService instance.
- Owns brisart_ai.knowledge.index.Index, brisart_ai.core.session_memory.
  SessionMemory, brisart_ai.core.settings.ResearchSettings, and one
  brisart_ai.knowledge.relevance_feedback.RelevanceFeedback.
- Calls brisart_ai.core.conversation.build_conversation_answer(),
  brisart_ai.knowledge.ingest.ingest_paths(), brisart_ai.knowledge.vault.*,
  brisart_ai.web.crawler.web_search_and_ingest().

Settings / parameters
---------------------
- __init__(db_path): construction deliberately unguarded.
- ask(text, force_web=None): forwards the session feedback store into the
  conversation router on every call.
- mark_relevant / mark_irrelevant: record a user's judgement on a source
  into the session store, so subsequent searches reflect it.
- _DIAGNOSTIC_MARKERS / _MAX_DIAGNOSTIC_LINES.

Edge cases
----------
- self._stdout_lock guards stdout redirection in ask().
- The feedback store starts empty, so it has no effect on ranking until a
  result is actually marked; marks last for the session, not across
  restarts.

Known limitations
-----------------
- The headless-testable seam between UI and engine; it orchestrates but
  owns no ranking logic itself.
- Diagnostic-marker handling recognizes only the fixed _DIAGNOSTIC_MARKERS
  set and caps output at _MAX_DIAGNOSTIC_LINES.
- Web research is gated by settings and runs synchronously; a slow
  provider blocks the calling turn.

Examples
--------
    >>> svc = BrisartService(index, memory, settings)   # doctest: +SKIP
    >>> print(svc.ask("who founded microsoft"))         # doctest: +SKIP
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
from brisart_ai.knowledge.relevance_feedback import RelevanceFeedback
from brisart_ai.knowledge.vault import add_note, list_notes, reindex_missing_notes, search_notes
from brisart_ai.web.crawler import web_search_and_ingest

_DIAGNOSTIC_MARKERS = ("WARN", "SKIP", "ERROR")
_MAX_DIAGNOSTIC_LINES = 5


class BrisartService:
    """Owns one Index, SessionMemory, ResearchSettings, and RelevanceFeedback
    for the app's lifetime."""
    def __init__(self, db_path: str = DEFAULT_DB):
        self.db_path = db_path
        self.index = Index(db_path)
        removed = self.index.purge_blocked_web_sources()
        if removed:
            print(f"Startup cleanup: removed {removed} stale dictionary/definition page(s) from the index.")
        reindexed = reindex_missing_notes(self.index)
        if reindexed:
            print(f"Startup cleanup: indexed {reindexed} previously unindexed note(s) for ranked search.")
        self.memory = SessionMemory(db_path)
        self.settings = ResearchSettings()
        self.feedback = RelevanceFeedback()
        self._stdout_lock = threading.Lock()
        self.last_diagnostics: List[str] = []

    def counts(self) -> Tuple[int, int, int]:
        total = self.index.source_count()
        files = self.index.source_count("file")
        web = self.index.source_count("web")
        return total, files, web

    def ask(self, text: str, limit: int = 8, web_limit: int = 5, force_web: Optional[bool] = None) -> str:
        """Answer a question, with the session feedback store applied to ranking."""
        resolved_force_web = (
            self.settings.get("auto_web_research") if force_web is None else bool(force_web)
        )
        buffer = io.StringIO()
        with self._stdout_lock:
            with contextlib.redirect_stdout(buffer):
                answer = build_conversation_answer(
                    text, self.index, self.memory, limit=limit,
                    settings=self.settings, web_limit=web_limit,
                    force_web=resolved_force_web, feedback=self.feedback,
                )
        self.last_diagnostics = self._extract_diagnostics(buffer.getvalue())
        return answer

    def mark_relevant(self, source_id, title: str) -> None:
        """Record that the user found a source relevant; nudges future ranking."""
        self.feedback.mark_relevant(source_id, title)

    def mark_irrelevant(self, source_id, title: str) -> None:
        """Record that the user found a source irrelevant; nudges future ranking."""
        self.feedback.mark_irrelevant(source_id, title)

    @staticmethod
    def _extract_diagnostics(captured_output: str) -> List[str]:
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


