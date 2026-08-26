"""Conversation router for BrisartAI.

Order of logic:
1. Clean accidental shell syntax from chat input.
2. Search indexed local data, honoring the Local Files and Research
   Notes settings toggles.
3. If a fresh web search is forced (``force_web=True``), or no local
   evidence exists and Automatic Web Research is enabled in settings,
   search the public web and re-check for evidence.
4. If evidence exists (local or newly fetched), synthesize a sourced
   answer.
5. If no evidence exists at all, answer with a simple grounding label
   instead of a conversational fallback.
"""
from __future__ import annotations

from typing import Optional

from brisart_ai.core.settings import ResearchSettings
from brisart_ai.io.input_cleaner import normalize_shellish_input
from brisart_ai.knowledge.ranker import search
from brisart_ai.knowledge.synthesizer import synthesize
from brisart_ai.web.crawler import web_search_and_ingest


def build_conversation_answer(
    query: str,
    index,
    memory,
    limit: int = 8,
    settings: Optional[ResearchSettings] = None,
    web_limit: int = 5,
    force_web: bool = False,
) -> str:
    """Build a source-grounded answer.

    When ``force_web`` is True, BrisartAI always searches the public web
    for the question first, then synthesizes an answer from whatever it
    finds. This is what the desktop UI uses so a user can simply type a
    question and get a web-grounded answer inline, without remembering a
    command or toggling a setting.

    When ``force_web`` is False, the older behavior applies: local
    evidence is used first, and the public web is only searched when no
    local evidence is found and ``auto_web_research`` is enabled.

    Local search is scoped by the ``search_local_files`` and
    ``search_notes`` settings via an explicit set of allowed source
    types passed to ``knowledge/ranker.search()``:
      * ``web`` is always included, so previously indexed web pages
        remain searchable regardless of the Local Files setting -- the
        local index never goes completely silent just because that
        toggle is off.
      * ``file`` is included only when ``search_local_files`` is on.
      * ``note`` is included only when ``search_notes`` is on. Saved
        notes are mirrored into the main source index by
        ``knowledge/vault.add_note()``/``reindex_missing_notes()``, so
        including "note" here gives them the exact same TF-IDF,
        coverage, title-match, phrase-match, and intent-aware ranking
        as files and web pages -- rather than the separate, cruder
        substring-count merge used previously.
    """
    cleaned = normalize_shellish_input(query)
    recent = memory.recent_topics(limit=4)

    allowed_source_types = {"web"}
    if settings is None or settings.get("search_local_files"):
        allowed_source_types.add("file")
    if settings is not None and settings.get("search_notes"):
        allowed_source_types.add("note")

    def _gather_docs():
        return search(
            index,
            cleaned,
            limit=limit,
            source_types=allowed_source_types,
        )

    docs = _gather_docs()

    auto_enabled = bool(
        settings is not None and settings.get("auto_web_research")
    )
    should_search_web = force_web or (not docs and auto_enabled)
    used_web = False
    if should_search_web:
        used_web = True
        web_search_and_ingest(
            cleaned,
            index,
            limit=web_limit,
            crawl_depth=0,
        )
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
