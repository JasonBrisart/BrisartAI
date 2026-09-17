"""
File: brisart_ai/core/conversation.py

Purpose
-------
The single answer-routing entry point.

Communication / relationships
------------------------------
- brisart_ai/ui/service.py: BrisartService.ask() is the only caller.
- Calls brisart_ai.io.input_cleaner.normalize_shellish_input(),
  brisart_ai.knowledge.ranker.search(),
  brisart_ai.knowledge.synthesizer.synthesize(), and
  brisart_ai.web.crawler.web_search_and_ingest().

Settings / parameters
----------------------
- allowed_source_types: always "web"; "file"/"note" per-toggle.
- force_web: explicit "Research Web" vs. fallback-only.

Edge cases
----------
- A web search is triggered exactly once per question.
- Both question and answer are always recorded to session memory.
"""
from __future__ import annotations

from typing import Optional

from brisart_ai.core.settings import ResearchSettings
from brisart_ai.io.input_cleaner import normalize_shellish_input
from brisart_ai.knowledge.ranker import search
from brisart_ai.knowledge.synthesizer import synthesize
from brisart_ai.web.crawler import web_search_and_ingest


def build_conversation_answer(
    query: str, index, memory, limit: int = 8,
    settings: Optional[ResearchSettings] = None, web_limit: int = 5,
    force_web: bool = False,
) -> str:
    """Build a source-grounded answer to one question."""
    cleaned = normalize_shellish_input(query)
    recent = memory.recent_topics(limit=4)

    allowed_source_types = {"web"}
    if settings is None or settings.get("search_local_files"):
        allowed_source_types.add("file")
    if settings is not None and settings.get("search_notes"):
        allowed_source_types.add("note")

    def _gather_docs():
        return search(index, cleaned, limit=limit, source_types=allowed_source_types)

    docs = _gather_docs()

    auto_enabled = bool(settings is not None and settings.get("auto_web_research"))
    should_search_web = force_web or (not docs and auto_enabled)

    used_web = False
    if should_search_web:
        used_web = True
        web_search_and_ingest(cleaned, index, limit=web_limit, crawl_depth=0)
        docs = _gather_docs()

    if docs:
        answer = synthesize(cleaned, docs, recent_topics=recent)
        if used_web:
            answer = (
                "Searched the public web for this question, then answered "
                "from the pages that were retrieved.\n\n"
            ) + answer
    else:
        answer = (
            "I don't have any indexed information that answers that yet. "
            "Try importing relevant files, or ask me to research the web "
            "for this."
        )
        if used_web:
            answer = (
                "I searched the public web for this, but did not find "
                "pages with usable, on-topic evidence. Try rephrasing the "
                "question with more specific terms."
            )

    memory.add("user", cleaned)
    memory.add("assistant", answer)

    return answer


__all__ = ["build_conversation_answer"]
