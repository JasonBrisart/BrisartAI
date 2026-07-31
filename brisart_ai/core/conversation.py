"""Conversation router for BrisartAI.

Order of logic:

1. Clean accidental shell syntax from chat input.
2. Answer self-knowledge questions directly.
3. Search indexed local data.
4. If a fresh web search is forced (``force_web=True``), or no local
   evidence exists and Automatic Web Research is enabled in settings,
   search the public web and re-check for evidence.
5. If evidence exists (local or newly fetched), synthesize a sourced
   answer.
6. If no evidence exists at all, answer conversationally with a clear
   grounding label.
"""

from __future__ import annotations

from typing import Optional

from brisart_ai.core.settings import ResearchSettings
from brisart_ai.intelligence.freeform import freeform_response
from brisart_ai.io.input_cleaner import normalize_shellish_input
from brisart_ai.intelligence.self_knowledge import (
    looks_like_self_question,
    self_response,
)
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
    """Build a source-grounded or conversational answer.

    When ``force_web`` is True, BrisartAI always searches the public web
    for the question first, then synthesizes an answer from whatever it
    finds. This is what the desktop UI uses so a user can simply type a
    question and get a web-grounded answer inline, without remembering a
    command or toggling a setting.

    When ``force_web`` is False, the older behavior applies: local
    evidence is used first, and the public web is only searched when no
    local evidence is found and ``auto_web_research`` is enabled.
    """

    cleaned = normalize_shellish_input(query)
    recent = memory.recent_topics(limit=4)

    if looks_like_self_question(cleaned):
        answer = self_response(cleaned, index=index, recent_topics=recent)
        memory.add("user", cleaned)
        memory.add("assistant", answer)
        return answer

    docs = search(index, cleaned, limit=limit)

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
        docs = search(index, cleaned, limit=limit)

    if docs:
        answer = synthesize(cleaned, docs, recent_topics=recent)
        if used_web:
            answer = (
                "Searched the public web for this question, then answered "
                "from the pages that were retrieved.\n\n"
            ) + answer
    else:
        answer = freeform_response(cleaned, index=index, recent_topics=recent)
        if used_web:
            answer += (
                "\n\nI searched the public web for this, but did not find "
                "pages with usable, on-topic evidence. Try rephrasing the "
                "question with more specific terms."
            )

    memory.add("user", cleaned)
    memory.add("assistant", answer)
    return answer


__all__ = ["build_conversation_answer"]
