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
from typing import List, Tuple
from brisart_ai.core.conversation import build_conversation_answer
from brisart_ai.core.session_memory import SessionMemory
from brisart_ai.core.settings import ResearchSettings, TOGGLE_LABELS
from brisart_ai.knowledge.index import DEFAULT_DB, Index
from brisart_ai.knowledge.ingest import ingest_paths
from brisart_ai.knowledge.vault import add_note, list_notes, search_notes
from brisart_ai.web.crawler import web_search_and_ingest
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
        force_web: bool = True,
    ) -> str:
        """Answer a question.

        By default the desktop UI forces a fresh public web search for
        every question (``force_web=True``) and then answers from the
        retrieved pages, so results always appear inline in the GUI
        without needing a separate command or the ``Automatic Web
        Research`` toggle. Imported files are searched the same way
        regardless of this flag, since they live in the same index as
        web pages.
        """
        return build_conversation_answer(
            text,
            self.index,
            self.memory,
            limit=limit,
            settings=self.settings,
            web_limit=web_limit,
            force_web=force_web,
        )
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