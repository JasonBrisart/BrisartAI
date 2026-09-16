"""
File: brisart_ai/knowledge/ranker.py

Purpose
-------
Retrieval + ranking over the local SQLite index. Computes a base term
score with the Brisart Relevance Engine (relevance_engine.py), then
layers coverage, title-match, generic-concept-title penalty, phrase-
match, proximity, and intent adjustments -- with query-term expansion,
spelling correction, authority tiers, a recency signal, session
relevance feedback, and a final MMR diversity pass all built directly
into the standard ranking path. Every stage returns the signals it
fired, so the replay scripts can explain any result.

Communication / relationships
------------------------------
- brisart_ai/core/conversation.py: build_conversation_answer() is the
  primary caller of search().
- Reads the sources/terms tables directly from knowledge.index.Index.
- Base scoring: knowledge.relevance_engine. Signal helpers: intent
  (detect_intent, score_intent, name_candidates,
  is_bare_generic_concept_title), text_normalize.expand_query_terms(),
  spelling (build_vocabulary, suggest_corrections),
  knowledge.authority.authority_multiplier(),
  knowledge.diversity.diversify_results().
- Session nudge: a knowledge.relevance_feedback.RelevanceFeedback owned
  by the service layer and passed in on every call.

Settings / parameters
---------------------
Term weights: STOPWORD_WEIGHT = 0.15; EXPANSION_WEIGHT = 0.5 (expansion-
only terms count half and are excluded from coverage).
Coverage: COVERAGE_FLOOR = 0.15 -- score *= FLOOR + (1-FLOOR)*coverage.
Intent: INTENT_WEIGHT = 0.30; factor clamped to [INTENT_MIN_FACTOR = 0.40,
INTENT_MAX_FACTOR = 1.90]; INTENT_TEXT_CHARS = 2000.
Title: TITLE_MATCH_WEIGHT = 0.12, capped TITLE_MATCH_MAX_FACTOR = 1.42;
GENERIC_TERM_DAMPING = 0.2.
Penalty/phrase: GENERIC_CONCEPT_TITLE_PENALTY_FACTOR = 0.35;
PHRASE_MATCH_FACTOR = 1.35 (>= PHRASE_MATCH_MIN_WORDS = 2 words).
Authority/recency (bounded): authority_multiplier in [0.85, 1.20];
RECENCY_MAX_BOOST = 0.08, RECENCY_HALFLIFE_DAYS = 45.0.
Feedback/diversity (standard): feedback.apply_feedback() is a +/-25%
session nudge, applied whenever the caller supplies a store; diversify
runs a final MMR re-order (DIVERSIFY_LAMBDA = 0.7) on every search.

Edge cases
----------
- An empty query or an all-stopword query returns [].
- Expansion terms and spelling suggestions are additive: the literal term
  is always searched; a "did_you_mean" map rides on every result.
- The MMR diversity pass is a pure re-order then trim-to-limit; it never
  re-scores a document, and its first pick is always the highest-scored
  document, so single-best-answer regressions are preserved.
- feedback with no recorded marks is a no-op (multiplier 1.0), so ranking
  is unchanged until the user actually marks a result.

Known limitations
-----------------
- All scoring weights/thresholds are hand-tuned constants, not learned.
- Ranking is lexical; there is no semantic/embedding retrieval, so a
  relevant doc sharing no surface vocabulary is unreachable (a recall
  ceiling, not a ranking bug).
- The recency signal uses indexed_at (index time), not the document's own
  publication date, which the crawler does not reliably extract.
- Expansion/spelling draw on finite hand-maintained vocabularies; gaps
  there limit recall broadening.
- The diversity pass is O(n^2) in the candidate pool.

Examples
--------
    >>> search(index, "")
    []
    >>> docs = search(index, "who invented microsoft?")
    >>> docs[0]["title"]
    'History of Microsoft'
    >>> r = search(index, "mircosoft")
    >>> "microsoft" in r[0]["did_you_mean"].get("mircosoft", [])
    True
"""
from __future__ import annotations

import collections
import math
import re
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from brisart_ai.intent import (
    INTENT_GENERAL, detect_intent, is_bare_generic_concept_title,
    name_candidates, score_intent,
)
from brisart_ai.knowledge import relevance_engine
from brisart_ai.knowledge.authority import authority_multiplier
from brisart_ai.knowledge.diversity import diversify_results
from brisart_ai.text_normalize import expand_query_terms
from brisart_ai.spelling import build_vocabulary, suggest_corrections
from brisart_ai.util import tokenize

STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an",
    "and", "any", "are", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "cannot", "did",
    "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is",
    "it", "its", "itself", "just", "many", "me", "more", "most", "much", "my",
    "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only",
    "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same",
    "she", "should", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "will", "with", "would", "you", "your", "yours", "yourself",
    "yourselves",
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
EXPANSION_WEIGHT = 0.5
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
RECENCY_MAX_BOOST = 0.08
RECENCY_HALFLIFE_DAYS = 45.0
DIVERSIFY_LAMBDA = 0.7
_SECONDS_PER_DAY = 86400.0
_PHRASE_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _normalize_for_phrase(text: str) -> str:
    return _PHRASE_NORMALIZE_RE.sub(" ", str(text or "").casefold()).strip()


def _term_weight(term: str, expansion_terms: Set[str]) -> float:
    if term in STOPWORDS:
        return STOPWORD_WEIGHT
    if term in expansion_terms:
        return EXPANSION_WEIGHT
    return 1.0


def title_match_adjust(title, meaningful_terms, term_rarity=None):
    if not title or not meaningful_terms:
        return (1.0, [])
    title_terms = set(tokenize(title)) & meaningful_terms
    if not title_terms:
        return (1.0, [])
    average_rarity = (sum(term_rarity.values()) / len(term_rarity)) if term_rarity else 1.0
    if average_rarity <= 0:
        average_rarity = 1.0
    weighted_total = 0.0
    matched = []
    for term in sorted(title_terms):
        rel = term_rarity.get(term, average_rarity) / average_rarity if term_rarity else 1.0
        if term in GENERIC_QUERY_VERBS:
            rel *= GENERIC_TERM_DAMPING
        weighted_total += rel
        matched.append(term)
    factor = min(TITLE_MATCH_MAX_FACTOR, 1.0 + (TITLE_MATCH_WEIGHT * weighted_total))
    return (factor, [f"{SIGNAL_TITLE_MATCH}:{','.join(matched)}"])


def generic_concept_title_adjust(title, location):
    for candidate in [title] + name_candidates(location or ""):
        if is_bare_generic_concept_title(candidate):
            return (GENERIC_CONCEPT_TITLE_PENALTY_FACTOR, [SIGNAL_GENERIC_CONCEPT_TITLE])
    return (1.0, [])


def phrase_match_adjust(query, haystack):
    nq = _normalize_for_phrase(query)
    if len(nq.split()) < PHRASE_MATCH_MIN_WORDS:
        return (1.0, [])
    if nq and nq in _normalize_for_phrase(haystack):
        return (PHRASE_MATCH_FACTOR, [SIGNAL_PHRASE_MATCH])
    return (1.0, [])


def proximity_adjust(matched_terms, haystack):
    return relevance_engine.proximity_bonus(haystack, matched_terms)


def _recency_multiplier(indexed_at: int, newest: int) -> float:
    """Bounded freshness signal: newest source gets +RECENCY_MAX_BOOST,
    decaying with a fixed half-life. Uniform-timestamp corpora are unaffected."""
    if not indexed_at or not newest or newest <= 0:
        return 1.0
    age_days = max(0.0, (newest - indexed_at) / _SECONDS_PER_DAY)
    decay = math.pow(0.5, age_days / RECENCY_HALFLIFE_DAYS)
    return 1.0 + RECENCY_MAX_BOOST * decay


def intent_adjust(base_score, title, text, location, intent, query,
                  topic_terms=None, term_rarity=None, matched_terms=None,
                  indexed_at=0, newest=0):
    haystack = " ".join(p for p in (str(title or ""), str(location or ""),
                                    str(text or "")[:INTENT_TEXT_CHARS]) if p)
    score = base_score
    boosts: List[str] = []
    penalties: List[str] = []

    tf, tb = title_match_adjust(title, topic_terms or set(), term_rarity)
    if tf != 1.0:
        score *= tf
        boosts.extend(tb)
    gf, gp = generic_concept_title_adjust(title, location)
    if gf != 1.0:
        score *= gf
        penalties.extend(gp)
    pf, pb = phrase_match_adjust(query, haystack)
    if pf != 1.0:
        score *= pf
        boosts.extend(pb)
    xf, xb = proximity_adjust(sorted(matched_terms or set()), haystack)
    if xf != 1.0:
        score *= xf
        boosts.extend(xb)

    af = authority_multiplier(location)
    if af != 1.0:
        score *= af
        (boosts if af > 1.0 else penalties).append(f"<authority>:{af:.2f}")
    rf = _recency_multiplier(indexed_at, newest)
    if rf != 1.0:
        score *= rf
        boosts.append(f"<recency>:{rf:.3f}")

    if intent == INTENT_GENERAL:
        return (score, boosts, penalties)
    delta, ib, ip = score_intent(haystack, intent, query, topic_terms=topic_terms)
    factor = max(INTENT_MIN_FACTOR, min(INTENT_MAX_FACTOR, 1.0 + (delta * INTENT_WEIGHT)))
    score *= factor
    boosts.extend(ib)
    penalties.extend(ip)
    return (score, boosts, penalties)


def _build_term_sql(source_types, source_type):
    if source_types:
        ph = ",".join(["?"] * len(source_types))
        return (f"SELECT terms.source_id, terms.tf FROM terms "
                f"JOIN sources ON sources.id = terms.source_id "
                f"WHERE terms.term = ? AND sources.source_type IN ({ph})")
    if source_type:
        return ("SELECT terms.source_id, terms.tf FROM terms "
                "JOIN sources ON sources.id = terms.source_id "
                "WHERE terms.term = ? AND sources.source_type = ?")
    return "SELECT source_id, tf FROM terms WHERE term = ?"


def _build_doc_length_sql(source_types, source_type):
    if source_types:
        ph = ",".join(["?"] * len(source_types))
        return (f"SELECT terms.source_id, SUM(terms.tf) AS total_terms FROM terms "
                f"JOIN sources ON sources.id = terms.source_id "
                f"WHERE sources.source_type IN ({ph}) GROUP BY terms.source_id")
    if source_type:
        return ("SELECT terms.source_id, SUM(terms.tf) AS total_terms FROM terms "
                "JOIN sources ON sources.id = terms.source_id "
                "WHERE sources.source_type = ? GROUP BY terms.source_id")
    return "SELECT source_id, SUM(tf) AS total_terms FROM terms GROUP BY source_id"


def _load_document_lengths(index, types_list, source_type):
    sql = _build_doc_length_sql(types_list, source_type)
    if types_list:
        rows = index.conn.execute(sql, tuple(types_list)).fetchall()
    elif source_type:
        rows = index.conn.execute(sql, (source_type,)).fetchall()
    else:
        rows = index.conn.execute(sql).fetchall()
    lengths = {sid: float(total or 0) for sid, total in rows}
    avg = (sum(lengths.values()) / len(lengths)) if lengths else 1.0
    return lengths, (avg if avg > 0 else 1.0)


def _corpus_vocabulary(index) -> Dict[str, int]:
    """term -> document frequency, for spelling-correction candidates."""
    try:
        rows = index.conn.execute(
            "SELECT term, COUNT(*) FROM terms GROUP BY term").fetchall()
    except Exception:
        return {}
    return {term: int(df) for term, df in rows}


def search(index, query: str, limit: int = 8, source_type: Optional[str] = None,
           source_types: Optional[Iterable[str]] = None,
           feedback=None, diversify_lambda: float = DIVERSIFY_LAMBDA):
    """Search indexed sources and rank matches. The full signal stack --
    query expansion, spelling correction, authority, recency, session
    relevance feedback, and MMR diversity -- is part of the standard
    ranking path; a feedback store with no recorded marks simply has no
    effect, and diversity's first pick is always the top-scored document."""
    original_terms = tokenize(query)
    if not original_terms:
        return []
    original_set = set(original_terms)

    # Additive query expansion. Expansion-only terms are down-weighted and
    # excluded from coverage so single-best-answer ranking is preserved.
    expanded = expand_query_terms(query)
    expansion_terms = {t for t in expanded if t not in original_set and t not in STOPWORDS}

    # Spelling correction for meaningful terms absent from the corpus.
    vocabulary = _corpus_vocabulary(index)
    correction_vocab = build_vocabulary(vocabulary)
    did_you_mean: Dict[str, List[str]] = {}
    for term in original_set:
        if term in STOPWORDS:
            continue
        if vocabulary.get(term, 0) == 0:
            suggestions = suggest_corrections(term, correction_vocab)
            if suggestions:
                did_you_mean[term] = suggestions
                for s in suggestions:
                    expansion_terms.add(s)

    unique_terms = original_set | expansion_terms
    meaningful_terms = {t for t in original_set if t not in STOPWORDS}
    meaningful_total = len(meaningful_terms)

    types_list = list(source_types) if source_types else None
    if types_list:
        total_sources = max(1, sum(index.source_count(t) for t in types_list))
    elif source_type:
        total_sources = max(1, index.source_count(source_type))
    else:
        total_sources = max(1, index.source_count())

    term_sql = _build_term_sql(types_list, source_type)
    doc_lengths, avg_len = _load_document_lengths(index, types_list, source_type)

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
        df = len(rows)
        if df == 0:
            continue
        rarity = relevance_engine.rarity_weight(df, total_sources)
        term_rarity[term] = rarity
        weight = _term_weight(term, expansion_terms)
        is_meaningful = term in meaningful_terms
        for sid, tf in rows:
            scores[sid] += weight * relevance_engine.term_contribution(tf, df, total_sources)
            if is_meaningful:
                matched_meaningful[sid].add(term)
    if not scores:
        return []

    for sid, raw in list(scores.items()):
        dl = doc_lengths.get(sid, avg_len)
        scores[sid] = raw * relevance_engine.shape_multiplier(dl, avg_len)

    adjusted: Dict[int, float] = {}
    for sid, base in scores.items():
        cov = (len(matched_meaningful[sid]) / meaningful_total) if meaningful_total > 0 else 1.0
        adjusted[sid] = base * (COVERAGE_FLOOR + (1.0 - COVERAGE_FLOOR) * cov)

    intent = detect_intent(query)
    pool = sorted(adjusted.items(), key=lambda kv: kv[1], reverse=True)[
        : max(0, limit) * INTENT_CANDIDATE_FACTOR + INTENT_CANDIDATE_MIN]

    rows_by_id: Dict[int, tuple] = {}
    reasons: Dict[int, Tuple[List[str], List[str]]] = {}
    newest = 0
    detail_rows = {}
    for sid, _base in pool:
        row = index.conn.execute(
            "SELECT source_type, location, title, text, extension, size_bytes, "
            "indexed_at FROM sources WHERE id = ?", (sid,)).fetchone()
        if row is None:
            continue
        detail_rows[sid] = row
        newest = max(newest, int(row[6] or 0))
    for sid, base in pool:
        row = detail_rows.get(sid)
        if row is None:
            continue
        rows_by_id[sid] = row
        new_score, boosts, penalties = intent_adjust(
            base, row[2] or row[1], row[3], row[1], intent, query,
            topic_terms=meaningful_terms, term_rarity=term_rarity,
            matched_terms=matched_meaningful.get(sid),
            indexed_at=int(row[6] or 0), newest=newest)
        adjusted[sid] = new_score
        reasons[sid] = (boosts, penalties)

    # Session relevance-feedback nudge (bounded), applied whenever the
    # service hands us its store. A store with no marks is a no-op.
    if feedback is not None:
        titles = {sid: (r[2] or r[1]) for sid, r in rows_by_id.items()}
        adjusted = {**adjusted, **feedback.apply_feedback(
            {sid: adjusted[sid] for sid in rows_by_id}, titles)}

    ranked = sorted(((sid, adjusted[sid]) for sid in rows_by_id),
                    key=lambda kv: kv[1], reverse=True)

    documents: List[Dict[str, object]] = []
    for sid, score in ranked:
        row = rows_by_id.get(sid)
        if row is None:
            continue
        b, p = reasons.get(sid, ([], []))
        documents.append({
            "id": sid, "score": score, "source_type": row[0], "location": row[1],
            "title": row[2] or row[1], "text": row[3], "extension": row[4],
            "size_bytes": row[5], "indexed_at": row[6], "intent": intent,
            "intent_boosts": b, "intent_penalties": p,
            "did_you_mean": did_you_mean,
        })

    # Final MMR diversity re-order, then trim to limit. First pick is always
    # the top-scored document, so single-best-answer results are preserved.
    documents = diversify_results(documents, lambda_param=diversify_lambda)[:max(0, limit)]

    return documents


__all__ = [
    "COVERAGE_FLOOR", "DIVERSIFY_LAMBDA", "GENERIC_CONCEPT_TITLE_PENALTY_FACTOR",
    "GENERIC_QUERY_VERBS", "GENERIC_TERM_DAMPING", "INTENT_MAX_FACTOR",
    "INTENT_MIN_FACTOR", "INTENT_TEXT_CHARS", "INTENT_WEIGHT", "PHRASE_MATCH_FACTOR",
    "PHRASE_MATCH_MIN_WORDS", "RECENCY_MAX_BOOST", "SIGNAL_GENERIC_CONCEPT_TITLE",
    "SIGNAL_PHRASE_MATCH", "SIGNAL_TITLE_MATCH", "STOPWORDS",
    "TITLE_MATCH_MAX_FACTOR", "TITLE_MATCH_WEIGHT", "generic_concept_title_adjust",
    "intent_adjust", "phrase_match_adjust", "proximity_adjust", "search",
    "title_match_adjust",
]


