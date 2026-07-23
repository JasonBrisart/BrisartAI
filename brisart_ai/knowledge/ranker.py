"""Retrieval and ranking for BrisartAI."""

from __future__ import annotations

import collections
import math
from typing import Dict, List, Optional

from brisart_ai.util import tokenize


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

    total_sources = max(
        1,
        index.source_count(source_type),
    )

    scores: Dict[int, float] = collections.defaultdict(float)

    for term in set(terms):
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

        for source_id, term_frequency in rows:
            adjusted_frequency = (
                1.0 + math.log(max(1, term_frequency))
            )

            scores[source_id] += (
                adjusted_frequency
                * inverse_document_frequency
            )

    ranked = sorted(
        scores.items(),
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