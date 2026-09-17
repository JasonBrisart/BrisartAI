"""
File: brisart_ai/knowledge/relevance_engine.py

Purpose
-------
Brisart Relevance Engine -- BrisartAI's own term-scoring engine,
replacing classic TF-IDF/BM25 math with small, named, fixed-value
lookup tables (rarity tiers, presence schedule, length-shape brackets)
plus a new proximity signal with no TF-IDF/BM25 equivalent at all.

Communication / relationships
------------------------------
- brisart_ai/knowledge/ranker.py: search() calls rarity_weight(),
  presence_points(), shape_multiplier(), proximity_bonus().
- Imports nothing from elsewhere in brisart_ai.

Settings / parameters
----------------------
- RARITY_TIERS: 4 fixed tiers by corpus-share.
- PRESENCE_SCHEDULE: 4 fixed points by occurrence count, capped.
- SHAPE_BRACKETS: 4 fixed multipliers by length ratio; shortest bracket
  BOOSTS (1.15x) unlike BM25.
- PROXIMITY_WINDOW_CHARS (120) / PROXIMITY_BONUS_PER_PAIR (0.15) /
  PROXIMITY_BONUS_CAP (0.6).

Edge cases
----------
- rarity_weight()/presence_points() return 0.0 for zero occurrences.
- shape_multiplier() guards average_length <= 0 by returning 1.0.
"""
from __future__ import annotations

import re
from typing import Dict, List, Sequence, Set, Tuple

RARITY_TIERS: Tuple[Tuple[float, float], ...] = (
    (0.20, 0.4), (0.05, 1.0), (0.01, 1.8), (0.00, 2.6),
)


def rarity_weight(document_frequency: int, total_documents: int) -> float:
    """Fixed-tier weight for a term's corpus rarity. Not a log curve."""
    if document_frequency <= 0 or total_documents <= 0:
        return 0.0
    share = document_frequency / total_documents
    for threshold, weight in RARITY_TIERS:
        if share >= threshold:
            return weight
    return RARITY_TIERS[-1][1]


PRESENCE_SCHEDULE: Tuple[Tuple[int, float], ...] = (
    (8, 1.6), (4, 1.5), (2, 1.3), (1, 1.0),
)


def presence_points(term_frequency: int) -> float:
    """Fixed-schedule credit for how many times a term occurs in one document."""
    if term_frequency <= 0:
        return 0.0
    for threshold, points in PRESENCE_SCHEDULE:
        if term_frequency >= threshold:
            return points
    return PRESENCE_SCHEDULE[-1][1]


def term_contribution(term_frequency: int, document_frequency: int, total_documents: int) -> float:
    """One term's total contribution to a document's base score."""
    return presence_points(term_frequency) * rarity_weight(document_frequency, total_documents)


SHAPE_BRACKETS: Tuple[Tuple[float, float], ...] = (
    (2.50, 0.55), (1.50, 0.75), (0.75, 1.00), (0.00, 1.15),
)


def shape_multiplier(document_length: float, average_length: float) -> float:
    """Fixed-bracket multiplier for a document's length relative to the corpus."""
    if average_length <= 0:
        return 1.0
    ratio = document_length / average_length
    for threshold, multiplier in SHAPE_BRACKETS:
        if ratio >= threshold:
            return multiplier
    return SHAPE_BRACKETS[-1][1]


PROXIMITY_WINDOW_CHARS = 120
PROXIMITY_BONUS_PER_PAIR = 0.15
PROXIMITY_BONUS_CAP = 0.6
SIGNAL_PROXIMITY = "<proximity>"

_WORD_BOUNDARY_RE = re.compile(r"[A-Za-z0-9]+")


def _term_positions(haystack: str, terms: Set[str]) -> Dict[str, List[int]]:
    positions: Dict[str, List[int]] = {}
    for match in _WORD_BOUNDARY_RE.finditer(haystack):
        word = match.group(0).casefold()
        if word in terms:
            positions.setdefault(word, []).append(match.start())
    return positions


def proximity_bonus(haystack: str, matched_terms: Sequence[str]) -> Tuple[float, List[str]]:
    """Bonus multiplier for matched query terms appearing physically close together."""
    distinct_terms = sorted(set(t.casefold() for t in matched_terms if t))
    if len(distinct_terms) < 2:
        return (1.0, [])

    positions = _term_positions(haystack, set(distinct_terms))
    qualifying_pairs = 0
    for i in range(len(distinct_terms)):
        for j in range(i + 1, len(distinct_terms)):
            left_positions = positions.get(distinct_terms[i])
            right_positions = positions.get(distinct_terms[j])
            if not left_positions or not right_positions:
                continue
            if _closest_distance(left_positions, right_positions) <= PROXIMITY_WINDOW_CHARS:
                qualifying_pairs += 1

    if qualifying_pairs == 0:
        return (1.0, [])
    bonus = min(PROXIMITY_BONUS_CAP, qualifying_pairs * PROXIMITY_BONUS_PER_PAIR)
    return (1.0 + bonus, [f"{SIGNAL_PROXIMITY}:{qualifying_pairs}"])


def _closest_distance(left_positions: Sequence[int], right_positions: Sequence[int]) -> int:
    best = None
    for left in left_positions:
        for right in right_positions:
            distance = abs(left - right)
            if best is None or distance < best:
                best = distance
    return best if best is not None else PROXIMITY_WINDOW_CHARS + 1


__all__ = [
    "PRESENCE_SCHEDULE", "PROXIMITY_BONUS_CAP", "PROXIMITY_BONUS_PER_PAIR",
    "PROXIMITY_WINDOW_CHARS", "RARITY_TIERS", "SHAPE_BRACKETS", "SIGNAL_PROXIMITY",
    "presence_points", "proximity_bonus", "rarity_weight", "shape_multiplier",
    "term_contribution",
]
