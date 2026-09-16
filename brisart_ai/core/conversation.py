"""
File: brisart_ai/core/conversation.py

Purpose
-------
Answer routing: the single "answer this question" entry point the UI
service calls. It cleans the input, decides which source types to search,
runs local ranked search (optionally falling back to, or forcing, one web
search), hands surviving evidence to synthesis, and records the exchange
to session memory. Compound questions are split into independent
sub-questions, each ranked + synthesized separately, with a single
CitationGraph shared across the sub-answers.

Communication / relationships
------------------------------
- brisart_ai/ui/service.py: BrisartService is the caller of
  build_conversation_answer(), and hands in the session's
  RelevanceFeedback store on every call, plus the force_web / auto_web
  flags (see below).
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
- web_limit (default 5): max pages a fallback/forced web search may ingest.
- force_web (default False): the EXPLICIT "Research Web" action. When True,
  one web_ingest() pass ALWAYS runs for every sub-question, then the index
  is re-searched -- even if local search already returned matches. This is
  what makes the "Research Web" button actually consult the web regardless
  of what is already indexed (see Fix 1).
- auto_web (default False): the "Automatic Web Research" setting. When True
  (and force_web is False), one web_ingest() pass runs ONLY when local
  search came up empty for that sub-question -- the documented fallback
  behavior. web is always an allowed source type; file is added when
  search_local_files is on, note when search_notes is on.
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
- force_web and auto_web are independent: force_web True always fetches;
  auto_web True fetches only on an empty local result set; both False
  never touch the network.

Known limitations
-----------------
- Decomposition splits at most once, so a three-clause question yields at
  most two parts.
- The shared CitationGraph is per-call and in-memory; corroboration is
  not persisted across turns.
- Fallback/forced web ingestion runs synchronously in the answer path; a
  slow provider directly delays that sub-question's answer.
- Sub-answers are concatenated, not merged; a source surfaced by two
  sub-questions is cited under each.
- In AUTO mode a stale or marginal local hit still suppresses the web
  fallback (auto_web only fires on an empty local result set, by
  documented design). A user who wants fresh web results despite an old
  local match should use the explicit "Research Web" action, which
  always fetches (see Fix 1).

Fix 1 (2026-09-16): Web research was gated on the local index being empty
for BOTH the explicit "Research Web" action and the automatic fallback.
The shipped condition was `if not docs and force_web and web_ingest is not
None:`, and ui/service.py collapsed the explicit action and the
auto_web_research setting into a single `force_web` bool. Consequently the
explicit "Research Web" button did NOTHING whenever any local page already
matched the query -- contradicting docs/README.md, which states the forced
action always searches the web -- and, more visibly to users, a single
stale or marginal page already sitting in the local index (e.g. an old
crawl of a cat-history page mentioning the 1600s) satisfied `not docs` and
silently suppressed the web search, so the answer was synthesized from that
stale page instead of fresh results. Fixed by splitting the single gate
into two independent flags: force_web (explicit action) always ingests,
auto_web (the setting) ingests only when local search is empty. ui/
service.py now passes them separately (force_web only for the "Research
Web" action; auto_web from the setting).

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
                              web_limit=5, force_web=False, auto_web=False,
                              web_ingest=None, feedback=None,
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

        # Web research. The EXPLICIT "Research Web" action (force_web) always
        # fetches fresh results, even when local search already matched --
        # so an old/marginal indexed page can never silently suppress it.
        # AUTOMATIC Web Research (auto_web) keeps its documented fallback
        # behavior: it only fetches when local search came up empty. Either
        # way, at most one web pass runs per sub-question, and the index is
        # re-searched afterward so freshly crawled pages are ranked in.
        want_web = web_ingest is not None and (force_web or (auto_web and not docs))
        if want_web:
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
