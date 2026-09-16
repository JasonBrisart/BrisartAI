"""
File: brisart_ai/knowledge/confidence.py

Purpose
-------
Computes an overall confidence score for a synthesized answer and detects
contradictions among the sentences chosen to support it -- the last stage
of the pipeline. Confidence answers "how much should the user trust
this?"; contradiction detection answers "do the chosen sentences agree?".
Glue over three modules (citation-graph corroboration, authority source-
tiers, and intent's negation-span detection); it reimplements none.

Communication / relationships
------------------------------
- knowledge/synthesizer.py: after final sentence selection, calls
  compute_confidence() and detect_contradictions() over the chosen
  (source_id, location, sentence) tuples and surfaces both in the answer.
- Imports intent.{detect_negation_spans, is_position_negated},
  knowledge.authority.classify_authority_tier(), and
  knowledge.citation_graph.CitationGraph for its three signals.

Settings / parameters
---------------------
- CONFIDENCE_WEIGHTS (sum to 1.0): source_count = 0.35, authority = 0.30,
  corroboration = 0.20, contradiction_penalty = 0.15 (subtracted).
- Source-count score (diminishing returns): 1 -> 0.4, 2 -> 0.7, 3+ -> 1.0;
  used for both the source_count and corroboration factors.
- Per-tier authority point values: governmental/academic = 1.0,
  encyclopedic = 0.9, established-news = 0.75, neutral = 0.55,
  low-value = 0.25 (averaged over the chosen sources' locations).
- contradiction_count contributes min(1.0, count * 0.5) to the penalty.
- _NUMERIC_CLAIM_RE pulls (subject, number) pairs for numeric
  contradiction checking (numbers/negation only, not general semantics).

Edge cases
----------
- compute_confidence([]) returns 0.0 -- never a misleading 0.5.
- A single source scores corroboration at its minimum but can still reach
  high overall confidence via a strong authority tier.
- detect_contradictions() never flags a source against itself and only
  compares sentences sharing a subject keyword.
- Only NUMERIC and NEGATION contradictions are detected; purely
  qualitative disagreement is a documented non-goal.

Known limitations
-----------------
- Contradiction detection catches only numeric and affirm-vs-negate
  mismatches; qualitative disagreement ("fast" vs "slow") is not caught.
- _NUMERIC_CLAIM_RE keys on a single leading subject word; differently-
  worded subjects with conflicting numbers are not matched.
- Authority tiering is host-based; a weak claim on a strong host scores
  the same as a strong one.
- The confidence weights are hand-tuned constants, not calibrated against
  labelled data.

Examples
--------
    >>> compute_confidence([])
    0.0
    >>> pair = [ChosenSentence(1, "https://a.com", "Microsoft founded in 1975."),
    ...         ChosenSentence(2, "https://b.com", "Microsoft founded in 1981.")]
    >>> detect_contradictions(pair)[0]["type"]
    'numeric'
"""
from __future__ import annotations
import re
from typing import Dict, List, Sequence, Tuple

from brisart_ai.intent import detect_negation_spans, is_position_negated
from brisart_ai.knowledge.authority import (
    TIER_ENCYCLOPEDIC, TIER_ESTABLISHED_NEWS, TIER_GOVERNMENTAL_ACADEMIC,
    TIER_LOW_VALUE, TIER_NEUTRAL, classify_authority_tier,
)
from brisart_ai.knowledge.citation_graph import CitationGraph

CONFIDENCE_WEIGHTS = {
    "source_count": 0.35, "authority": 0.30,
    "corroboration": 0.20, "contradiction_penalty": 0.15,
}
_AUTHORITY_SCORES = {
    TIER_GOVERNMENTAL_ACADEMIC: 1.0, TIER_ENCYCLOPEDIC: 0.9,
    TIER_ESTABLISHED_NEWS: 0.75, TIER_NEUTRAL: 0.55, TIER_LOW_VALUE: 0.25,
}
_NUMERIC_CLAIM_RE = re.compile(
    r"(?P<subject>[a-z][a-z\-]{2,20})\s+(?:in|since|on|by|at|to)?\s*"
    r"(?P<number>\d{1,4}(?:[.,]\d+)?)", re.IGNORECASE)


class ChosenSentence:
    __slots__ = ("source_id", "location", "sentence")

    def __init__(self, source_id, location: str, sentence: str):
        self.source_id = source_id
        self.location = location
        self.sentence = sentence


def _score_source_count(n: int) -> float:
    if n <= 0:
        return 0.0
    if n == 1:
        return 0.4
    if n == 2:
        return 0.7
    return 1.0


def _score_authority(locations: Sequence[str]) -> float:
    if not locations:
        return 0.0
    scores = [_AUTHORITY_SCORES.get(classify_authority_tier(loc), 0.55) for loc in locations]
    return sum(scores) / len(scores)


def compute_confidence(chosen, topic="", graph: CitationGraph = None,
                       contradiction_count: int = 0) -> float:
    if not chosen:
        return 0.0
    distinct = {c.source_id for c in chosen}
    locations = [c.location for c in chosen]
    source_score = _score_source_count(len(distinct))
    authority_score = _score_authority(locations)
    if graph is not None and topic:
        corroboration_score = _score_source_count(graph.corroboration_count(topic))
    else:
        corroboration_score = _score_source_count(len(distinct))
    penalty = min(1.0, contradiction_count * 0.5)
    weighted = (CONFIDENCE_WEIGHTS["source_count"] * source_score
                + CONFIDENCE_WEIGHTS["authority"] * authority_score
                + CONFIDENCE_WEIGHTS["corroboration"] * corroboration_score
                - CONFIDENCE_WEIGHTS["contradiction_penalty"] * penalty)
    return max(0.0, min(1.0, weighted))


def _numeric_claims(sentence: str) -> List[Tuple[str, str]]:
    return [(m.group("subject").casefold(), m.group("number"))
            for m in _NUMERIC_CLAIM_RE.finditer(sentence or "")]


def detect_contradictions(chosen: Sequence[ChosenSentence]) -> List[Dict]:
    out: List[Dict] = []
    n = len(chosen)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = chosen[i], chosen[j]
            if a.source_id == b.source_id:
                continue
            for asub, anum in _numeric_claims(a.sentence):
                for bsub, bnum in _numeric_claims(b.sentence):
                    if asub == bsub and anum != bnum:
                        out.append({"type": "numeric", "subject": asub,
                                    "left_source": a.source_id, "left_value": anum,
                                    "right_source": b.source_id, "right_value": bnum})
    return out


def detect_negation_contradiction(chosen: Sequence[ChosenSentence], query_term: str) -> List[Dict]:
    affirmed, negated = [], []
    for item in chosen:
        m = re.search(re.escape(query_term), item.sentence, re.IGNORECASE)
        if not m:
            continue
        if is_position_negated(m.start(), detect_negation_spans(item.sentence)):
            negated.append(item.source_id)
        else:
            affirmed.append(item.source_id)
    if affirmed and negated:
        return [{"type": "negation", "term": query_term,
                 "affirmed_by": affirmed, "negated_by": negated}]
    return []


__all__ = ["CONFIDENCE_WEIGHTS", "ChosenSentence", "compute_confidence",
           "detect_contradictions", "detect_negation_contradiction"]


