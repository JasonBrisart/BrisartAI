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
"""

from __future__ import annotations

import collections
import math
from typing import Dict, List, Optional, Set

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


def _term_weight(term: str) -> float:
    """Return the ranking weight for a single query term."""
    return STOPWORD_WEIGHT if term in STOPWORDS else 1.0


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

    ranked = sorted(
        adjusted_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:max(0, limit)]

    documents: List[Dict[str, object]] = []
    for source_id, score in ranked:
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
            }
        )
    return documents


__all__ = ["STOPWORDS", "search"]
