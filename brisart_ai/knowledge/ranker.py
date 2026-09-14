"""
File: brisart_ai/knowledge/ranker.py

Purpose
-------
Retrieval and ranking over BrisartAI's local index -- the Brisart
Relevance Engine's base term score, layered with coverage, title-match,
generic-concept-title penalty, phrase-match, proximity, and intent
adjustments.

Communication / relationships
------------------------------
- brisart_ai/core/conversation.py: build_conversation_answer() calls search().
- brisart_ai/web/crawler.py: imports phrase_match_adjust().
- Imports brisart_ai.knowledge.relevance_engine, brisart_ai.intent.*,
  brisart_ai.util.tokenize().

Settings / parameters
----------------------
- STOPWORD_WEIGHT (0.15) / COVERAGE_FLOOR (0.15).
- INTENT_WEIGHT (0.30) / INTENT_MIN_FACTOR (0.40) / INTENT_MAX_FACTOR (1.90).
- TITLE_MATCH_WEIGHT (0.12) / TITLE_MATCH_MAX_FACTOR (1.42) /
  GENERIC_TERM_DAMPING (0.2).
- GENERIC_CONCEPT_TITLE_PENALTY_FACTOR (0.35).
- PHRASE_MATCH_FACTOR (1.35) / PHRASE_MATCH_MIN_WORDS (2).

Edge cases
----------
- search() accepts source_type or source_types.
- proximity_adjust() needs 2+ distinct matched terms.
"""
from __future__ import annotations

import collections
import re
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from brisart_ai.intent import (
    INTENT_GENERAL, detect_intent, is_bare_generic_concept_title,
    name_candidates, score_intent,
)
from brisart_ai.knowledge import relevance_engine
from brisart_ai.util import tokenize

STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am",
    "an", "and", "any", "are", "as", "at", "be", "because", "been",
    "before", "being", "below", "between", "both", "but", "by", "can",
    "cannot", "did", "do", "does", "doing", "down", "during",
    "each", "few", "for", "from", "further", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself",
    "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself",
    "just", "many", "me", "more", "most", "much", "my", "myself", "no",
    "nor", "not", "now", "of", "off", "on", "once", "only", "or",
    "other", "our", "ours", "ourselves", "out", "over", "own", "same",
    "she", "should", "so", "some", "such", "than", "that", "the",
    "their", "theirs", "them", "themselves", "then", "there", "these",
    "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "will", "with", "would", "you",
    "your", "yours", "yourself", "yourselves",
}

GENERIC_QUERY_VERBS: Set[str] = {
    "explain", "explains", "explained", "explanation", "describe", "describes",
    "described", "description", "define", "defines", "defined", "definition",
    "meaning", "meanings", "tell", "tells", "give", "gives", "summarize",
    "summarizes", "summarise", "summarises", "outline", "outlines", "elaborate",
    "elaborates", "clarify", "clarifies", "understand", "understands", "know",
    "knows", "find", "finds", "show", "shows", "list", "lists",
}

STOPWORD_WEIGHT = 0.15
COVERAGE_FLOOR = 0.15
INTENT_WEIGHT = 0.30
INTENT_MIN_FACTOR = 0.40
INTENT_MAX_FACTOR = 1.90
INTENT_TEXT_CHARS = 2000
INTENT_CANDIDATE_FACTOR = 5
INTENT_CANDIDATE_MIN = 10
TITLE_MATCH_WEIGHT = 0.12
TITLE_MATCH_MAX_FACTOR = 1.42
GENERIC_TERM_DAMPING = 0.2
SIGNAL_TITLE_MATCH = "<title-match>"
GENERIC_CONCEPT_TITLE_PENALTY_FACTOR = 0.35
SIGNAL_GENERIC_CONCEPT_TITLE = "<generic-concept-title>"
PHRASE_MATCH_FACTOR = 1.35
PHRASE_MATCH_MIN_WORDS = 2
SIGNAL_PHRASE_MATCH = "<phrase-match>"

_PHRASE_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _normalize_for_phrase(text: str) -> str:
    return _PHRASE_NORMALIZE_RE.sub(" ", str(text or "").casefold()).strip()


def _term_weight(term: str) -> float:
    return STOPWORD_WEIGHT if term in STOPWORDS else 1.0


def title_match_adjust(
    title: str, meaningful_terms: Set[str], term_rarity: Optional[Dict[str, float]] = None,
) -> Tuple[float, List[str]]:
    """Boost a score for meaningful query terms present in the title."""
    if not title or not meaningful_terms:
        return (1.0, [])
    title_terms = set(tokenize(title)) & meaningful_terms
    if not title_terms:
        return (1.0, [])

    average_rarity = (sum(term_rarity.values()) / len(term_rarity)) if term_rarity else 1.0
    if average_rarity <= 0:
        average_rarity = 1.0

    weighted_total = 0.0
    matched_terms: List[str] = []
    for term in sorted(title_terms):
        relative_weight = 1.0
        if term_rarity:
            relative_weight = term_rarity.get(term, average_rarity) / average_rarity
        if term in GENERIC_QUERY_VERBS:
            relative_weight *= GENERIC_TERM_DAMPING
        weighted_total += relative_weight
        matched_terms.append(term)

    factor = min(TITLE_MATCH_MAX_FACTOR, 1.0 + (TITLE_MATCH_WEIGHT * weighted_total))
    return (factor, [f"{SIGNAL_TITLE_MATCH}:{','.join(matched_terms)}"])


def generic_concept_title_adjust(title: str, location: str) -> Tuple[float, List[str]]:
    """Penalize a document whose title/URL is a bare generic concept."""
    candidates = [title] + name_candidates(location or "")
    for candidate in candidates:
        if is_bare_generic_concept_title(candidate):
            return (GENERIC_CONCEPT_TITLE_PENALTY_FACTOR, [SIGNAL_GENERIC_CONCEPT_TITLE])
    return (1.0, [])


def phrase_match_adjust(query: str, haystack: str) -> Tuple[float, List[str]]:
    """Boost a score when the literal query phrase appears verbatim."""
    normalized_query = _normalize_for_phrase(query)
    if len(normalized_query.split()) < PHRASE_MATCH_MIN_WORDS:
        return (1.0, [])
    normalized_haystack = _normalize_for_phrase(haystack)
    if normalized_query and normalized_query in normalized_haystack:
        return (PHRASE_MATCH_FACTOR, [SIGNAL_PHRASE_MATCH])
    return (1.0, [])


def proximity_adjust(matched_terms: Sequence[str], haystack: str) -> Tuple[float, List[str]]:
    """Boost a score when matched query terms sit close together."""
    return relevance_engine.proximity_bonus(haystack, matched_terms)


def intent_adjust(
    base_score: float, title: str, text: str, location: str, intent: str, query: str,
    topic_terms: Optional[Set[str]] = None, term_rarity: Optional[Dict[str, float]] = None,
    matched_terms: Optional[Set[str]] = None,
) -> Tuple[float, List[str], List[str]]:
    """Apply title-match, generic-concept, phrase-match, proximity, and intent adjustments."""
    haystack = " ".join(
        part for part in (str(title or ""), str(location or ""), str(text or "")[:INTENT_TEXT_CHARS]) if part
    )

    score = base_score
    boosts: List[str] = []
    penalties: List[str] = []

    title_factor, title_boosts = title_match_adjust(title, topic_terms or set(), term_rarity)
    if title_factor != 1.0:
        score *= title_factor
        boosts.extend(title_boosts)

    generic_factor, generic_penalties = generic_concept_title_adjust(title, location)
    if generic_factor != 1.0:
        score *= generic_factor
        penalties.extend(generic_penalties)

    phrase_factor, phrase_boosts = phrase_match_adjust(query, haystack)
    if phrase_factor != 1.0:
        score *= phrase_factor
        boosts.extend(phrase_boosts)

    proximity_factor, proximity_boosts = proximity_adjust(sorted(matched_terms or set()), haystack)
    if proximity_factor != 1.0:
        score *= proximity_factor
        boosts.extend(proximity_boosts)

    if intent == INTENT_GENERAL:
        return (score, boosts, penalties)

    delta, intent_boosts, intent_penalties = score_intent(haystack, intent, query, topic_terms=topic_terms)
    factor = 1.0 + (delta * INTENT_WEIGHT)
    factor = max(INTENT_MIN_FACTOR, min(INTENT_MAX_FACTOR, factor))
    score *= factor
    boosts.extend(intent_boosts)
    penalties.extend(intent_penalties)

    return (score, boosts, penalties)


def _build_term_sql(source_types: Optional[Iterable[str]], source_type: Optional[str]) -> str:
    if source_types:
        placeholders = ",".join(["?"] * len(source_types))
        return f"""SELECT terms.source_id, terms.tf FROM terms
            JOIN sources ON sources.id = terms.source_id
            WHERE terms.term = ? AND sources.source_type IN ({placeholders})"""
    if source_type:
        return """SELECT terms.source_id, terms.tf FROM terms
            JOIN sources ON sources.id = terms.source_id
            WHERE terms.term = ? AND sources.source_type = ?"""
    return "SELECT source_id, tf FROM terms WHERE term = ?"


def _build_doc_length_sql(source_types: Optional[Iterable[str]], source_type: Optional[str]) -> str:
    if source_types:
        placeholders = ",".join(["?"] * len(source_types))
        return f"""SELECT terms.source_id, SUM(terms.tf) AS total_terms FROM terms
            JOIN sources ON sources.id = terms.source_id
            WHERE sources.source_type IN ({placeholders}) GROUP BY terms.source_id"""
    if source_type:
        return """SELECT terms.source_id, SUM(terms.tf) AS total_terms FROM terms
            JOIN sources ON sources.id = terms.source_id
            WHERE sources.source_type = ? GROUP BY terms.source_id"""
    return "SELECT source_id, SUM(tf) AS total_terms FROM terms GROUP BY source_id"


def _load_document_lengths(
    index, types_list: Optional[List[str]], source_type: Optional[str],
) -> Tuple[Dict[int, float], float]:
    doc_length_sql = _build_doc_length_sql(types_list, source_type)
    if types_list:
        rows = index.conn.execute(doc_length_sql, tuple(types_list)).fetchall()
    elif source_type:
        rows = index.conn.execute(doc_length_sql, (source_type,)).fetchall()
    else:
        rows = index.conn.execute(doc_length_sql).fetchall()
    lengths: Dict[int, float] = {sid: float(total or 0) for sid, total in rows}
    average_length = (sum(lengths.values()) / len(lengths)) if lengths else 1.0
    if average_length <= 0:
        average_length = 1.0
    return lengths, average_length


def search(
    index, query: str, limit: int = 8, source_type: Optional[str] = None,
    source_types: Optional[Iterable[str]] = None,
) -> List[Dict[str, object]]:
    """Search indexed sources and rank matches by relevance."""
    terms = tokenize(query)
    if not terms:
        return []

    unique_terms = set(terms)
    meaningful_terms = {term for term in unique_terms if term not in STOPWORDS}
    meaningful_total = len(meaningful_terms)

    types_list = list(source_types) if source_types else None
    if types_list:
        total_sources = max(1, sum(index.source_count(t) for t in types_list))
    elif source_type:
        total_sources = max(1, index.source_count(source_type))
    else:
        total_sources = max(1, index.source_count())

    term_sql = _build_term_sql(types_list, source_type)
    doc_lengths, average_doc_length = _load_document_lengths(index, types_list, source_type)

    scores: Dict[int, float] = collections.defaultdict(float)
    matched_meaningful: Dict[int, Set[str]] = collections.defaultdict(set)
    term_rarity: Dict[str, float] = {}

    for term in unique_terms:
        if types_list:
            rows = index.conn.execute(term_sql, (term, *types_list)).fetchall()
        elif source_type:
            rows = index.conn.execute(term_sql, (term, source_type)).fetchall()
        else:
            rows = index.conn.execute(term_sql, (term,)).fetchall()

        document_frequency = len(rows)
        if document_frequency == 0:
            continue

        rarity = relevance_engine.rarity_weight(document_frequency, total_sources)
        term_rarity[term] = rarity
        weight = _term_weight(term)
        is_meaningful = term not in STOPWORDS

        for source_id, term_frequency in rows:
            contribution = relevance_engine.term_contribution(term_frequency, document_frequency, total_sources)
            scores[source_id] += weight * contribution
            if is_meaningful:
                matched_meaningful[source_id].add(term)

    if not scores:
        return []

    for source_id, raw_score in list(scores.items()):
        doc_length = doc_lengths.get(source_id, average_doc_length)
        scores[source_id] = raw_score * relevance_engine.shape_multiplier(doc_length, average_doc_length)

    adjusted_scores: Dict[int, float] = {}
    for source_id, base_score in scores.items():
        coverage = (
            len(matched_meaningful[source_id]) / meaningful_total if meaningful_total > 0 else 1.0
        )
        multiplier = COVERAGE_FLOOR + (1.0 - COVERAGE_FLOOR) * coverage
        adjusted_scores[source_id] = base_score * multiplier

    intent = detect_intent(query)
    candidate_pool = sorted(adjusted_scores.items(), key=lambda item: item[1], reverse=True)[
        : max(0, limit) * INTENT_CANDIDATE_FACTOR + INTENT_CANDIDATE_MIN]

    rows_by_id: Dict[int, tuple] = {}
    reasons: Dict[int, Tuple[List[str], List[str]]] = {}

    for source_id, base_score in candidate_pool:
        row = index.conn.execute(
            "SELECT source_type, location, title, text, extension, size_bytes, indexed_at FROM sources WHERE id = ?",
            (source_id,),
        ).fetchone()
        if row is None:
            continue
        rows_by_id[source_id] = row

        new_score, boosts, penalties = intent_adjust(
            base_score, row[2] or row[1], row[3], row[1], intent, query,
            topic_terms=meaningful_terms, term_rarity=term_rarity,
            matched_terms=matched_meaningful.get(source_id),
        )
        adjusted_scores[source_id] = new_score
        reasons[source_id] = (boosts, penalties)

    ranked = sorted(
        ((source_id, adjusted_scores[source_id]) for source_id in rows_by_id),
        key=lambda item: item[1], reverse=True,
    )[:max(0, limit)]

    documents: List[Dict[str, object]] = []
    for source_id, score in ranked:
        row = rows_by_id.get(source_id)
        if row is None:
            continue
        boosts, penalties = reasons.get(source_id, ([], []))
        documents.append({
            "id": source_id, "score": score, "source_type": row[0], "location": row[1],
            "title": row[2] or row[1], "text": row[3], "extension": row[4],
            "size_bytes": row[5], "indexed_at": row[6], "intent": intent,
            "intent_boosts": boosts, "intent_penalties": penalties,
        })
    return documents


__all__ = [
    "COVERAGE_FLOOR", "GENERIC_CONCEPT_TITLE_PENALTY_FACTOR", "GENERIC_QUERY_VERBS",
    "GENERIC_TERM_DAMPING", "INTENT_MAX_FACTOR", "INTENT_MIN_FACTOR",
    "INTENT_TEXT_CHARS", "INTENT_WEIGHT", "PHRASE_MATCH_FACTOR",
    "PHRASE_MATCH_MIN_WORDS", "SIGNAL_GENERIC_CONCEPT_TITLE", "SIGNAL_PHRASE_MATCH",
    "SIGNAL_TITLE_MATCH", "STOPWORDS", "TITLE_MATCH_MAX_FACTOR", "TITLE_MATCH_WEIGHT",
    "generic_concept_title_adjust", "intent_adjust", "phrase_match_adjust",
    "proximity_adjust", "search", "title_match_adjust",
]
