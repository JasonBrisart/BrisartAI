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
  brisart_ai.web.crawler.web_search_and_ingest(). The last of these is
  passed INTO build_conversation_answer() as its web_ingest callback, so
  the conversation router can actually perform a fallback/forced web
  search (see Fix 1) -- without this wiring, force_web / auto_web_research
  are inert.

Settings / parameters
---------------------
- __init__(db_path): construction deliberately unguarded.
- ask(text, force_web=None): forwards the session feedback store into the
  conversation router on every call, passes web_search_and_ingest as the
  web_ingest callback so web research can actually run, and refreshes
  self.last_citations with that answer's structured citation data
  (source_id/title/location per [N] marker), via conversation.py's
  citation_sink parameter. force_web is a three-state flag: None means an
  ordinary typed question (defer to the Automatic Web Research setting);
  True means the explicit "Research Web" action (always fetch, even when
  the local index already matched). These are now forwarded to
  build_conversation_answer() as two SEPARATE flags -- force_web (explicit)
  and auto_web (setting) -- rather than one collapsed bool (see Fix 2).
- mark_relevant / mark_irrelevant: record a user's judgement on a source
  into the session store, so subsequent searches reflect it.
- mark_citation(index, relevant): the UI-facing entry point -- looks up
  self.last_citations by its 1-based running index (not the in-text
  bracket number, which can repeat across sub-questions) and calls
  mark_relevant()/mark_irrelevant() with the right source_id/title.
- _DIAGNOSTIC_MARKERS / _MAX_DIAGNOSTIC_LINES.

Edge cases
----------
- self._stdout_lock guards stdout redirection in ask().
- The feedback store starts empty, so it has no effect on ranking until a
  result is actually marked; marks last for the session, not across
  restarts.
- The explicit "Research Web" action fetches fresh web results even when
  the local index already contains a match; Automatic Web Research only
  fetches when local search comes up empty (see Fix 2).

Known limitations
-----------------
- The headless-testable seam between UI and engine; it orchestrates but
  owns no ranking logic itself.
- Diagnostic-marker handling recognizes only the fixed _DIAGNOSTIC_MARKERS
  set and caps output at _MAX_DIAGNOSTIC_LINES.
- Web research is gated by settings and runs synchronously; a slow
  provider blocks the calling turn.

Fix 1 (2026-09-16): Web research never actually ran from the chat box.
build_conversation_answer()'s only web-search branch is guarded by a
`web_ingest is not None` check, and its web_ingest parameter defaults to
None. ask() forwarded force_web, feedback, and citation_sink but never
passed web_ingest, so the guard was always False -- the crawler
(web_search_and_ingest, already imported in this module) was never called.
The GUI still printed "Searching the public web..." because app.py prints
that line from the setting alone, independent of whether a fetch occurs,
which masked the dead wire. Fixed by passing
`web_ingest=web_search_and_ingest` into build_conversation_answer() here.

Fix 2 (2026-09-16): The explicit "Research Web" action and the Automatic
Web Research setting were collapsed into a single `force_web` bool
(`resolved_force_web`), and build_conversation_answer() only ran a web
search when the local index was empty (`if not docs and force_web`).
Consequently the explicit "Research Web" button did nothing whenever any
local page already matched the query (contradicting docs/README.md, which
says the forced action always searches the web), and a single stale or
marginal page already in the local index silently suppressed the web
search for typed questions, so answers were synthesized from that stale
page (the reported "old cat-history" answers to statistic questions).
Fixed here by forwarding two SEPARATE flags to build_conversation_answer():
`force_web` (True only for the explicit action -> always fetch) and
`auto_web` (the setting -> fetch only when local search is empty). The
matching gate change lives in core/conversation.py's own Fix 1.

Examples
--------
    >>> svc = BrisartService(index, memory, settings)   # doctest: +SKIP
    >>> print(svc.ask("who founded microsoft"))         # doctest: +SKIP
"""

from __future__ import annotations

import contextlib
import io
import threading
from typing import Dict, List, Optional, Tuple

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
        self.last_citations: List[Dict[str, object]] = []

    def counts(self) -> Tuple[int, int, int]:
        total = self.index.source_count()
        files = self.index.source_count("file")
        web = self.index.source_count("web")
        return total, files, web

    def ask(self, text: str, limit: int = 8, web_limit: int = 5, force_web: Optional[bool] = None) -> str:
        """Answer a question, with the session feedback store applied to
        ranking and web research actually wired in.

        force_web=None means an ordinary typed question (defer to the
        Automatic Web Research setting); force_web=True means the explicit
        "Research Web" action, which always fetches fresh web results even
        when the local index already matched. These are forwarded to
        build_conversation_answer() as two separate flags -- force_web
        (explicit) and auto_web (setting) -- so a stale local match can no
        longer silently suppress the explicit action (see Fix 2).

        Also refreshes self.last_citations with the structured
        (source_id, title, location) data behind THIS answer's [N] markers,
        so the UI can offer a mark-relevant/irrelevant control per citation
        without parsing the answer text itself."""
        explicit_web = force_web is True
        auto_web = self.settings.get("auto_web_research")
        citation_sink: List[Dict[str, object]] = []
        buffer = io.StringIO()
        with self._stdout_lock:
            with contextlib.redirect_stdout(buffer):
                answer = build_conversation_answer(
                    text, self.index, self.memory, limit=limit,
                    settings=self.settings, web_limit=web_limit,
                    force_web=explicit_web, auto_web=auto_web,
                    web_ingest=web_search_and_ingest,
                    feedback=self.feedback, citation_sink=citation_sink,
                )
        self.last_diagnostics = self._extract_diagnostics(buffer.getvalue())
        for index, entry in enumerate(citation_sink, start=1):
            entry["index"] = index
        self.last_citations = citation_sink
        return answer

    def mark_relevant(self, source_id, title: str) -> None:
        """Record that the user found a source relevant; nudges future ranking."""
        self.feedback.mark_relevant(source_id, title)

    def mark_irrelevant(self, source_id, title: str) -> None:
        """Record that the user found a source irrelevant; nudges future ranking."""
        self.feedback.mark_irrelevant(source_id, title)

    def mark_citation(self, index: int, relevant: bool) -> Optional[Dict[str, object]]:
        """Mark a citation from the MOST RECENT ask() answer, by its 1-based
        position in self.last_citations (the running "citation index" the UI
        shows -- NOT the possibly-duplicated in-text "[N]" bracket number,
        which can repeat across sub-questions in a compound answer). Returns
        the matched citation dict, or None if no citation has that index."""
        for entry in self.last_citations:
            if entry.get("index") == index:
                if relevant:
                    self.mark_relevant(entry["source_id"], str(entry.get("title", "")))
                else:
                    self.mark_irrelevant(entry["source_id"], str(entry.get("title", "")))
                return entry
        return None

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
