"""Retrieval and ranking for BrisartAI.

Ranking model (pure Python, no dependencies):

1. Query terms are split into *meaningful* terms and *stopwords*.
   Stopwords -- ultra-common function/question words like "how", "many",
   "the", "is" -- are kept (so a query like "how many cats" still works)
   but weighted down hard, because a page that is merely dense in the
   word "many" is almost never the answer to a real question.

2. Each matching source accumulates a TF-IDF style score, with the
   stopword down-weight applied per term.

3. A *coverage* multiplier then rewards documents that match MORE of the
   distinct meaningful query terms. A dictionary page for the word
   "many" matches zero meaningful terms from "how many cats are in
   america" (cats, america) and is pushed to the bottom; a real
   cat-population page that matches both "cats" and "america" rises to
   the top. This coverage signal is what actually stops the "definition
   of many" hijack.

4. An *intent* adjustment from :mod:`brisart_ai.intent` is applied last.
   Steps 1-3 only measure whether a document mentions the query's words;
   they cannot tell WHY it mentions them. For "who invented microsoft"
   an imported PowerPoint manual and a company history both match
   "microsoft", and the manual can easily win on term frequency alone.
   The intent layer supplies the missing genre signal, boosting
   founder/history vocabulary and demoting product/account vocabulary.

   This is the same module the web ranker uses, so offline retrieval and
   public web search cannot drift apart. That mattered here: three copies
   of the dictionary blocklist had already rotted independently before
   being consolidated, and duplicating intent rules would repeat that.
"""

from __future__ import annotations

import collections
import math
from typing import Dict, List, Optional, Set, Tuple

from brisart_ai.intent import (
    INTENT_GENERAL,
    detect_intent,
    score_intent,
)
from brisart_ai.util import tokenize


# Ultra-common English function words and question words. These are not
# dropped from the query (so short natural questions still match), but
# they contribute very little to ranking on their own.
STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am",
    "an", "and", "any", "are", "as", "at", "be", "because", "been",
    "before", "being", "below", "between", "both", "but", "by", "can",
    "cannot", "could", "did", "do", "does", "doing", "down", "during",
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

# How much a stopword term counts relative to a meaningful term.
STOPWORD_WEIGHT = 0.15

# Coverage multiplier bounds. A document that matches none of the
# meaningful query terms keeps only COVERAGE_FLOOR of its base score; a
# document that matches all of them keeps the full score.
COVERAGE_FLOOR = 0.15

# Weight of one intent point, expressed as a fraction of a document's own
# base score rather than as a flat constant. TF-IDF scores have no fixed
# scale -- they grow with corpus size and document length -- so a flat
# bonus would be decisive in a small index and negligible in a large one.
# A proportional adjustment behaves consistently in both.
INTENT_WEIGHT = 0.30

# Clamp on the total intent adjustment. Intent is a hint, not a verdict:
# a document can lose at most 60% of its score for looking like the wrong
# genre and gain at most 90% for looking right. Without the floor a
# heavily penalized document could invert past zero and sort below
# genuinely unrelated noise.
INTENT_MIN_FACTOR = 0.40
INTENT_MAX_FACTOR = 1.90

# How much document body text feeds the intent check. The title carries
# the clearest genre signal, but the body is where "founded by Bill Gates
# and Paul Allen" or "an estimated 73.8 million pet cats" actually
# appears, which is exactly the evidence an offline chunk needs. Bounded
# so scoring stays fast and a long document cannot accumulate boosts
# without limit.
INTENT_TEXT_CHARS = 2000

# Size of the candidate pool that gets the intent pass, as a multiple of
# the requested limit (plus a floor). The intent signal lives in title and
# body text, so a candidate must be fetched to be judged -- scoring the
# entire index would mean reading every row on every query. A pool several
# times the limit is enough for a genuinely better document to climb into
# the results without that cost.
INTENT_CANDIDATE_FACTOR = 5
INTENT_CANDIDATE_MIN = 10


def _term_weight(term: str) -> float:
    """Return the ranking weight for a single query term."""
    return STOPWORD_WEIGHT if term in STOPWORDS else 1.0


def intent_adjust(
    base_score: float,
    title: str,
    text: str,
    location: str,
    intent: str,
    query: str,
    topic_terms: Optional[Set[str]] = None,
) -> Tuple[float, List[str], List[str]]:
    """Apply the shared intent adjustment to one document's base score.

    Returns ``(adjusted_score, boosts_hit, penalties_hit)``. Kept separate
    from :func:`search` so ``scripts/debug_offline_replay.py`` can score
    fixture chunks with no database involved, and so the adjustment is
    directly unit-testable.

    Title, location and a bounded prefix of the body are scored together:
    the title states the genre, the location often repeats it, and the
    body holds the concrete evidence (named founders, a year, a figure).
    """
    if intent == INTENT_GENERAL:
        return (base_score, [], [])

    haystack = " ".join(
        part
        for part in (
            str(title or ""),
            str(location or ""),
            str(text or "")[:INTENT_TEXT_CHARS],
        )
        if part
    )
    delta, boosts, penalties = score_intent(
        haystack,
        intent,
        query,
        topic_terms=topic_terms,
    )
    factor = 1.0 + (delta * INTENT_WEIGHT)
    factor = max(INTENT_MIN_FACTOR, min(INTENT_MAX_FACTOR, factor))
    return (base_score * factor, boosts, penalties)


def search(
    index,
    query: str,
    limit: int = 8,
    source_type: Optional[str] = None,
) -> List[Dict[str, object]]:
    """Search indexed sources and rank matches by term relevance."""
    terms = tokenize(query)
    if not terms:
        return []

    unique_terms = set(terms)
    meaningful_terms = {
        term for term in unique_terms if term not in STOPWORDS
    }
    meaningful_total = len(meaningful_terms)

    total_sources = max(
        1,
        index.source_count(source_type),
    )

    scores: Dict[int, float] = collections.defaultdict(float)
    # Track which distinct meaningful terms each source matched, so we
    # can reward broad topical coverage rather than raw repetition of a
    # single common word.
    matched_meaningful: Dict[int, Set[str]] = collections.defaultdict(set)

    for term in unique_terms:
        if source_type:
            rows = index.conn.execute(
                """
                SELECT
                    terms.source_id,
                    terms.tf
                FROM terms
                JOIN sources
                    ON sources.id = terms.source_id
                WHERE terms.term = ?
                  AND sources.source_type = ?
                """,
                (term, source_type),
            ).fetchall()
        else:
            rows = index.conn.execute(
                """
                SELECT source_id, tf
                FROM terms
                WHERE term = ?
                """,
                (term,),
            ).fetchall()

        document_frequency = len(rows)
        if document_frequency == 0:
            continue

        inverse_document_frequency = (
            math.log(
                (total_sources + 1)
                / (document_frequency + 1)
            )
            + 1.0
        )
        weight = _term_weight(term)
        is_meaningful = term not in STOPWORDS

        for source_id, term_frequency in rows:
            adjusted_frequency = (
                1.0 + math.log(max(1, term_frequency))
            )
            scores[source_id] += (
                weight
                * adjusted_frequency
                * inverse_document_frequency
            )
            if is_meaningful:
                matched_meaningful[source_id].add(term)

    if not scores:
        return []

    # Apply the coverage multiplier: reward documents that match more of
    # the distinct meaningful query terms.
    adjusted_scores: Dict[int, float] = {}
    for source_id, base_score in scores.items():
        if meaningful_total > 0:
            coverage = len(matched_meaningful[source_id]) / meaningful_total
        else:
            # Query was entirely stopwords (e.g. "how many"); nothing to
            # discriminate on, so leave the base score unmodified.
            coverage = 1.0
        multiplier = COVERAGE_FLOOR + (1.0 - COVERAGE_FLOOR) * coverage
        adjusted_scores[source_id] = base_score * multiplier

    # Intent pass. Every candidate is fetched before the final sort,
    # because the intent signal lives in the title and body text rather
    # than in the term table. Only a bounded candidate pool is considered
    # -- ordering the whole index by intent would mean reading every row.
    intent = detect_intent(query)
    candidate_pool = sorted(
        adjusted_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )[: max(0, limit) * INTENT_CANDIDATE_FACTOR + INTENT_CANDIDATE_MIN]

    rows_by_id: Dict[int, tuple] = {}
    reasons: Dict[int, Tuple[List[str], List[str]]] = {}
    for source_id, base_score in candidate_pool:
        row = index.conn.execute(
            """
            SELECT
                source_type,
                location,
                title,
                text,
                extension,
                size_bytes,
                indexed_at
            FROM sources
            WHERE id = ?
            """,
            (source_id,),
        ).fetchone()
        if row is None:
            continue
        rows_by_id[source_id] = row
        if intent != INTENT_GENERAL:
            new_score, boosts, penalties = intent_adjust(
                base_score,
                row[2] or row[1],
                row[3],
                row[1],
                intent,
                query,
                topic_terms=meaningful_terms,
            )
            adjusted_scores[source_id] = new_score
            reasons[source_id] = (boosts, penalties)

    ranked = sorted(
        (
            (source_id, adjusted_scores[source_id])
            for source_id in rows_by_id
        ),
        key=lambda item: item[1],
        reverse=True,
    )[:max(0, limit)]

    documents: List[Dict[str, object]] = []
    for source_id, score in ranked:
        row = rows_by_id.get(source_id)
        if row is None:
            continue
        boosts, penalties = reasons.get(source_id, ([], []))
        documents.append(
            {
                "id": source_id,
                "score": score,
                "source_type": row[0],
                "location": row[1],
                "title": row[2] or row[1],
                "text": row[3],
                "extension": row[4],
                "size_bytes": row[5],
                "indexed_at": row[6],
                "intent": intent,
                "intent_boosts": boosts,
                "intent_penalties": penalties,
            }
        )
    return documents


__all__ = [
    "COVERAGE_FLOOR",
    "INTENT_MAX_FACTOR",
    "INTENT_MIN_FACTOR",
    "INTENT_TEXT_CHARS",
    "INTENT_WEIGHT",
    "STOPWORDS",
    "intent_adjust",
    "search",
]
