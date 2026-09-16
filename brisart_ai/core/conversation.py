"""
File: brisart_ai/core/conversation.py

Purpose
-------
Answer routing: the single "answer this question" entry point the UI
service calls. It cleans the input, decides which source types to search,
runs local ranked search (optionally falling back to one web search),
hands surviving evidence to synthesis, and records the exchange to
session memory. Compound questions are split into independent
sub-questions, each ranked + synthesized separately, with a single
CitationGraph shared across the sub-answers.

Communication / relationships
------------------------------
- brisart_ai/ui/service.py: BrisartService is the caller of
  build_conversation_answer(), and hands in the session's
  RelevanceFeedback store on every call.
- Calls io.input_cleaner.normalize_shellish_input(),
  knowledge.query_decomposition.decompose_query(),
  knowledge.ranker.search(), and knowledge.synthesizer.synthesize().
- Constructs one knowledge.citation_graph.CitationGraph per question and
  shares it across every sub-question's synthesize() call.
- Reads core.settings.ResearchSettings for the allowed source-type set
  and core.session_memory for recent topics.

Settings / parameters
---------------------
- limit (default 8): max ranked documents pulled per sub-question.
- web_limit (default 5): max pages a fallback web search may ingest.
- force_web (default False): when True and local search is empty, one
  web_ingest() pass runs before re-searching. web is always an allowed
  source type; file is added when search_local_files is on, note when
  search_notes is on.
- feedback: the session RelevanceFeedback store, forwarded into every
  search so ranking always reflects the user's marks.
- At most ONE web search per sub-question, never stacked.
- citation_sink (default None): when a caller passes a list, it is
  populated with one {"display", "source_id", "title", "location",
  "subquestion"} dict per cited source across every sub-question
  (subquestion is None for a single, non-compound question, otherwise
  the sub-question text) -- purely additive; the return value is always
  the same plain str answer, and a None sink is zero behavior change.

Edge cases
----------
- An empty/whitespace-only sub-question from decomposition is skipped.
- When nothing is found across every sub-question, a single "no indexed
  information" message is returned, and both the question and that
  message are still recorded to session memory.
- A single-element decomposition is answered as a plain question, with no
  "[sub-question]" prefixing.
- feedback=None is accepted (a store with no marks would be a no-op
  anyway), so the router still works if the caller has not built one.

Known limitations
-----------------
- Decomposition splits at most once, so a three-clause question yields at
  most two parts.
- The shared CitationGraph is per-call and in-memory; corroboration is
  not persisted across turns.
- Fallback web ingestion runs synchronously in the answer path; a slow
  provider directly delays that sub-question's answer.
- Sub-answers are concatenated, not merged; a source surfaced by two
  sub-questions is cited under each.

Examples
--------
    >>> answer = build_conversation_answer(
    ...     "who founded microsoft?", index, memory, settings=settings,
    ...     feedback=feedback)
    >>> "Sources:" in answer
    True
    >>> answer = build_conversation_answer(
    ...     "who founded microsoft and when was it founded?",
    ...     index, memory, settings=settings, feedback=feedback)
    >>> answer.count("[who founded") >= 1
    True
"""
from __future__ import annotations
from typing import Dict, List, Optional
from brisart_ai.core.settings import ResearchSettings
from brisart_ai.io.input_cleaner import normalize_shellish_input
from brisart_ai.knowledge.citation_graph import CitationGraph
from brisart_ai.knowledge.query_decomposition import decompose_query
from brisart_ai.knowledge.ranker import search
from brisart_ai.knowledge.synthesizer import synthesize


def build_conversation_answer(query, index, memory, limit=8,
                              settings: Optional[ResearchSettings] = None,
                              web_limit=5, force_web=False, web_ingest=None,
                              feedback=None,
                              citation_sink: Optional[List[Dict[str, object]]] = None) -> str:
    cleaned = normalize_shellish_input(query)
    recent = memory.recent_topics(limit=4)
    allowed = {"web"}
    if settings is None or settings.get("search_local_files"):
        allowed.add("file")
    if settings is not None and settings.get("search_notes"):
        allowed.add("note")

    subquestions = decompose_query(cleaned)
    graph = CitationGraph()
    answers = []
    any_found = False
    for sub in subquestions:
        if not sub.strip():
            continue
        docs = search(index, sub, limit=limit, source_types=allowed, feedback=feedback)
        if not docs and force_web and web_ingest is not None:
            web_ingest(sub, index, limit=web_limit, crawl_depth=0)
            docs = search(index, sub, limit=limit, source_types=allowed, feedback=feedback)
        if docs:
            any_found = True
            sub_citations: Optional[List[Dict[str, object]]] = [] if citation_sink is not None else None
            piece = synthesize(sub, docs, recent_topics=recent, citation_graph=graph,
                              citation_sink=sub_citations)
            if citation_sink is not None and sub_citations:
                is_compound = len(subquestions) > 1
                for entry in sub_citations:
                    entry["subquestion"] = sub if is_compound else None
                citation_sink.extend(sub_citations)
            if len(subquestions) > 1:
                answers.append(f"[{sub}]\n{piece}")
            else:
                answers.append(piece)

    if any_found:
        answer = "\n\n".join(answers)
    else:
        answer = ("I don't have any indexed information that answers that yet. "
                  "Try importing relevant files, or ask me to research the web for this.")
    memory.add("user", cleaned)
    memory.add("assistant", answer)
    return answer


__all__ = ["build_conversation_answer"]



