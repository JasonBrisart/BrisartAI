"""
File: brisart_ai/core/conversation.py

Purpose
-------
The single answer-routing entry point: given a question, decide what to
search and how to turn it into an answer. Cleans the input, runs a
local ranked search scoped by which source types the user's settings
allow, optionally triggers exactly one web search (forced or as a
fallback when local search is empty and Automatic Web Research is on),
and hands surviving evidence to synthesis.

Communication / relationships
------------------------------
- brisart_ai/ui/service.py: BrisartService.ask() is the only caller of
  build_conversation_answer().
- Calls brisart_ai.io.input_cleaner.normalize_shellish_input(),
  brisart_ai.knowledge.ranker.search(),
  brisart_ai.knowledge.synthesizer.synthesize(), and
  brisart_ai.web.crawler.web_search_and_ingest().
- Reads brisart_ai.core.settings.ResearchSettings via the settings
  parameter, and reads/writes brisart_ai.core.session_memory.
  SessionMemory via the memory parameter.

Settings / parameters
----------------------
- allowed_source_types: always includes "web" (previously-indexed pages
  stay searchable regardless of the Local Files toggle), and adds
  "file"/"note" based on settings.search_local_files/search_notes --
  notes are mirrored into the main index by knowledge/vault.py's
  add_note(), so they get the exact same TF-IDF/coverage/title/phrase/
  intent-aware ranking as files and web pages rather than a separate
  cruder substring scan.
- force_web: when True (the explicit "Research Web" action), always
  triggers a fresh web search regardless of local results; when omitted/
  False, a web search runs only as a fallback when local search returns
  nothing AND settings.auto_web_research is on.

Edge cases
----------
- A web search is triggered exactly once per question -- never a forced
  search stacked on top of a redundant fallback search.
- When a web search runs and finds something, the answer gets a
  one-line "searched the web" notice; when it runs and finds nothing
  usable, a distinct message explains that (different cause than
  "nothing indexed yet" -- an attempt was made and failed, vs. no
  attempt was made at all).
- Both the question and the answer are always recorded to session
  memory, even on the "nothing found" path.
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
    """Build a source-grounded answer to one question."""
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
