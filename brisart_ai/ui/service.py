"""GUI-facing service layer for BrisartAI.

Widgets in ui/ never touch Index, SessionMemory, or ResearchSettings
directly. Everything routes through BrisartService so the desktop UI
and the terminal chat share the exact same backend logic (ingestion,
search, settings, vault, etc.) instead of duplicating it.
"""

from __future__ import annotations

from typing import List, Tuple

from brisart_ai.core.conversation import build_conversation_answer
from brisart_ai.core.session_memory import SessionMemory
from brisart_ai.core.settings import ResearchSettings, TOGGLE_LABELS
from brisart_ai.knowledge.analyzer import analyze_index
from brisart_ai.knowledge.index import DEFAULT_DB, Index
from brisart_ai.knowledge.ingest import ingest_paths
from brisart_ai.knowledge.project_awareness import project_report, research_report
from brisart_ai.knowledge.vault import (
    add_note,
    add_sources_to_collection,
    create_collection,
    list_collections,
    list_notes,
    rebuild_entities,
    search_notes,
    timeline,
    vault_report,
)
from brisart_ai.recommendations.recommender import recommend
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
        Research`` toggle.
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
    def add_note(self, title: str, body: str, collection: str = "") -> str:
        return add_note(self.index, title, body, collection)

    def list_notes(self, limit: int = 20) -> str:
        return list_notes(self.index, limit=limit)

    def search_notes(self, query: str, limit: int = 10) -> str:
        return search_notes(self.index, query, limit=limit)

    # -- collections --------------------------------------------------------
    def create_collection(self, name: str, description: str = "") -> str:
        return create_collection(self.index, name, description)

    def list_collections(self) -> str:
        return list_collections(self.index)

    def add_to_collection(self, name: str, query: str) -> str:
        return add_sources_to_collection(self.index, name, query)

    # -- reports --------------------------------------------------------------
    def vault_report(self) -> str:
        return vault_report(self.index)

    def rebuild_entities(self) -> str:
        return rebuild_entities(self.index)

    def project_report(self) -> str:
        return project_report(self.index)

    def research_report(self, top_terms: int = 35) -> str:
        return research_report(self.index, top_terms=top_terms)

    def analyze(self, top_terms: int = 25) -> str:
        return analyze_index(self.index, top_terms=top_terms)

    def recommend(self, top_terms: int = 20) -> str:
        return recommend(self.index, top_terms=top_terms)

    def timeline(self, query: str, limit: int = 30) -> str:
        return timeline(self.index, query, limit=limit)

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
