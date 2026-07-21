"""Retrieval and ranking."""

from __future__ import annotations

import collections
import math
from typing import Dict, List, Optional

from .util import tokenize


def search(index, query: str, limit: int = 8, source_type: Optional[str] = None) -> List[Dict[str, object]]:
    terms = tokenize(query)
    if not terms:
        return []

    total_sources = max(1, index.source_count(source_type))
    scores: Dict[int, float] = collections.defaultdict(float)

    for term in set(terms):
        if source_type:
            rows = index.conn.execute(
                """
                SELECT terms.source_id, terms.tf
                FROM terms
                JOIN sources ON sources.id = terms.source_id
                WHERE terms.term=? AND sources.source_type=?
                """,
                (term, source_type),
            ).fetchall()
        else:
            rows = index.conn.execute("SELECT source_id, tf FROM terms WHERE term=?", (term,)).fetchall()
        df = len(rows)
        if not df:
            continue
        idf = math.log((total_sources + 1) / (df + 1)) + 1.0
        for source_id, tf in rows:
            scores[source_id] += (1 + math.log(tf)) * idf

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
    docs = []
    for source_id, score in ranked:
        row = index.conn.execute(
            "SELECT source_type, location, title, text, extension, size_bytes, indexed_at FROM sources WHERE id=?",
            (source_id,),
        ).fetchone()
        if row:
            docs.append({
                "id": source_id,
                "score": score,
                "source_type": row[0],
                "location": row[1],
                "title": row[2] or row[1],
                "text": row[3],
                "extension": row[4],
                "size_bytes": row[5],
                "indexed_at": row[6],
            })
    return docs
