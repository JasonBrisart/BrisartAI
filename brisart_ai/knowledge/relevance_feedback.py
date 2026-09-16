"""
File: brisart_ai/knowledge/relevance_feedback.py

Purpose
-------
Bounded, session-scoped relevance feedback: when a user explicitly
marks a result as relevant or irrelevant, this module lets FUTURE
searches in the SAME session nudge similar documents up or down --
without ever letting feedback silently override the Brisart Relevance
Engine's own scoring, and without persisting across sessions (no
long-term "reputation" is built for a document from a single click).
This is a conservative, Rocchio-lite term-reweighting scheme: marking
a document relevant adds a small positive weight to the terms in ITS
title for the rest of the session; marking one irrelevant adds a small
negative weight. Both are capped, both decay to nothing once the
session ends, and neither can force the ranker to a specific document
or exclude one outright.

Communication / relationships
------------------------------
- ui/service.py: BrisartService constructs one RelevanceFeedback in
  __init__(), alongside the SessionMemory instance it already owns (see
  core/session_memory.py), giving it the same per-session lifetime.
  mark_relevant()/mark_irrelevant() record a user's judgement into it.
- knowledge/ranker.py: search() calls apply_feedback(scores, titles) as
  the last step in its signal stack, in the same position
  generic_concept_title_adjust() etc. already occupy, so feedback is one
  more bounded multiplier, not a replacement for ranking.
- Imports only the stdlib (collections); no dependency on any other
  brisart_ai module.

Settings / parameters
----------------------
- RELEVANT_TERM_WEIGHT (+0.20) / IRRELEVANT_TERM_WEIGHT (-0.20): the
  per-mark adjustment added to a term's running feedback weight.
  Symmetric and small, so a single mis-click has limited impact and
  several consistent marks are needed to meaningfully shift results.
- MAX_TERM_WEIGHT / MIN_TERM_WEIGHT (+0.60 / -0.60): a hard cap on how
  far any one term's accumulated weight can drift, regardless of how
  many times it has been marked -- this is what keeps feedback a NUDGE
  rather than a filter; even a heavily down-voted term can only
  suppress a document's score by at most FEEDBACK_MAX_ADJUSTMENT.
- FEEDBACK_MAX_ADJUSTMENT (+/-25%): the bounded multiplier range
  apply_feedback() can apply to any single document's score, computed
  from the SUM of matched terms' feedback weights, then clamped.
- Feedback state (RelevanceFeedback instances) is explicitly NOT
  persisted to SQLite or any file -- it exists only for the lifetime of
  the Python object holding it, which in the intended integration is
  exactly one running session. This is a deliberate scope limitation,
  not an oversight: cross-session feedback would require a much more
  careful design (whose feedback, how long it should last, how it
  interacts with re-indexed content) that this module does not attempt.

Edge cases
----------
- mark_relevant()/mark_irrelevant() operate on a document's TITLE terms
  only (via a caller-supplied tokenizer), not its full body text, since
  reinforcing every term in a long document's body risks the same
  keyword-stuffing failure mode the Brisart Relevance Engine's presence
  schedule was built to resist (see relevance_engine.py's own
  docstring) -- title terms are a much smaller, more deliberate
  signal.
- apply_feedback() never changes the RELATIVE order implied by a zero
  net feedback weight: a document whose title terms have no recorded
  feedback at all passes through with multiplier exactly 1.0.
- Marking the SAME document relevant multiple times in a session does
  not compound past MAX_TERM_WEIGHT/MIN_TERM_WEIGHT -- weights are
  clamped on every update, not just at read time.

Known limitations
-----------------
- Session-scoped and in-memory only; feedback is intentionally NOT
  persisted across restarts (cross-session feedback is an unsolved
  design question here, not an oversight).
- Reinforces on TITLE terms only, not body text, to avoid rewarding
  keyword-stuffed bodies.
- Every adjustment is clamped to [MIN_TERM_WEIGHT, MAX_TERM_WEIGHT] and
  the net multiplier to +/-FEEDBACK_MAX_ADJUSTMENT, so feedback is a
  nudge and can never pin or exclude a document.

Examples
--------
    >>> fb = RelevanceFeedback()
    >>> fb.mark_irrelevant(2, "Microsoft account login")
    >>> fb.feedback_multiplier("Microsoft account login") < 1.0
    True
    >>> fb.feedback_multiplier("Unrelated title")
    1.0
"""
from __future__ import annotations
from typing import Callable, Dict, Iterable, Set

RELEVANT_TERM_WEIGHT = 0.20
IRRELEVANT_TERM_WEIGHT = -0.20
MAX_TERM_WEIGHT = 0.60
MIN_TERM_WEIGHT = -0.60
FEEDBACK_MAX_ADJUSTMENT = 0.25  # +/-25%


def _default_tokenizer(text: str) -> Set[str]:
    return {w.casefold() for w in str(text or "").split() if len(w) > 1}


class RelevanceFeedback:
    """Bounded, session-scoped term-weight feedback store."""

    def __init__(self, tokenizer: Callable[[str], Iterable[str]] = _default_tokenizer):
        self._tokenizer = tokenizer
        self._term_weights: Dict[str, float] = {}
        self._marked_relevant: Set = set()
        self._marked_irrelevant: Set = set()

    def _adjust(self, title: str, delta: float) -> None:
        for term in self._tokenizer(title):
            current = self._term_weights.get(term, 0.0)
            updated = max(MIN_TERM_WEIGHT, min(MAX_TERM_WEIGHT, current + delta))
            self._term_weights[term] = updated

    def mark_relevant(self, source_id, title: str) -> None:
        if not title:
            return
        self._marked_relevant.add(source_id)
        self._marked_irrelevant.discard(source_id)
        self._adjust(title, RELEVANT_TERM_WEIGHT)

    def mark_irrelevant(self, source_id, title: str) -> None:
        if not title:
            return
        self._marked_irrelevant.add(source_id)
        self._marked_relevant.discard(source_id)
        self._adjust(title, IRRELEVANT_TERM_WEIGHT)

    def term_weight(self, term: str) -> float:
        return self._term_weights.get(term.casefold(), 0.0)

    def feedback_multiplier(self, title: str) -> float:
        """Bounded multiplier in [1 - FEEDBACK_MAX_ADJUSTMENT,
        1 + FEEDBACK_MAX_ADJUSTMENT] for a document with the given
        title, derived from the sum of its title terms' feedback
        weights."""
        terms = self._tokenizer(title)
        if not terms:
            return 1.0
        total = sum(self._term_weights.get(term, 0.0) for term in terms)
        # Normalize by term count so a long title doesn't automatically
        # accumulate a larger adjustment than a short one.
        average = total / len(terms)
        bounded = max(-FEEDBACK_MAX_ADJUSTMENT, min(FEEDBACK_MAX_ADJUSTMENT, average))
        return 1.0 + bounded

    def apply_feedback(self, scored_documents: Dict[int, float], titles: Dict[int, str]) -> Dict[int, float]:
        """Apply feedback_multiplier() to every document in
        `scored_documents`, keyed by source_id, using `titles` to look
        up each document's title."""
        adjusted: Dict[int, float] = {}
        for source_id, score in scored_documents.items():
            title = titles.get(source_id, "")
            adjusted[source_id] = score * self.feedback_multiplier(title)
        return adjusted

    def reset(self) -> None:
        self._term_weights.clear()
        self._marked_relevant.clear()
        self._marked_irrelevant.clear()


def _self_test() -> None:
    fb = RelevanceFeedback()
    assert fb.feedback_multiplier("History of Microsoft") == 1.0

    fb.mark_relevant(1, "History of Microsoft")
    assert fb.term_weight("microsoft") == RELEVANT_TERM_WEIGHT
    assert fb.feedback_multiplier("History of Microsoft") > 1.0

    fb.mark_irrelevant(2, "Microsoft Account Login")
    assert fb.term_weight("login") == IRRELEVANT_TERM_WEIGHT
    assert fb.feedback_multiplier("Microsoft Account Login") < 1.0

    # repeated marking clamps, never exceeds bounds
    for _ in range(20):
        fb.mark_relevant(1, "History of Microsoft")
    assert fb.term_weight("microsoft") <= MAX_TERM_WEIGHT

    for _ in range(20):
        fb.mark_irrelevant(2, "Microsoft Account Login")
    assert fb.term_weight("login") >= MIN_TERM_WEIGHT

    # apply_feedback respects bounded range
    scores = {1: 10.0, 2: 10.0, 3: 10.0}
    titles = {1: "History of Microsoft", 2: "Microsoft Account Login", 3: "Unrelated Page"}
    adjusted = fb.apply_feedback(scores, titles)
    assert adjusted[1] > 10.0
    assert adjusted[2] < 10.0
    assert adjusted[3] == 10.0  # no recorded feedback for its terms
    for source_id, score in adjusted.items():
        multiplier = score / scores[source_id]
        assert 1 - FEEDBACK_MAX_ADJUSTMENT - 1e-9 <= multiplier <= 1 + FEEDBACK_MAX_ADJUSTMENT + 1e-9

    fb.reset()
    assert fb.feedback_multiplier("History of Microsoft") == 1.0


if __name__ == "__main__":
    _self_test()
    print("relevance_feedback self-test passed.")


__all__ = [
    "RELEVANT_TERM_WEIGHT", "IRRELEVANT_TERM_WEIGHT", "MAX_TERM_WEIGHT",
    "MIN_TERM_WEIGHT", "FEEDBACK_MAX_ADJUSTMENT", "RelevanceFeedback",
]


