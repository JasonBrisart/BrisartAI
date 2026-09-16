"""
File: brisart_ai/knowledge/citation_graph.py

Purpose
-------
Tracks which sources have been cited together for which topics, so
BrisartAI can answer "how many independent sources actually support
this?" instead of just "how many sentences did the synthesizer pick?"
A topic answered by three sentences that all happen to come from the
SAME underlying source is a single-source risk, not three-way
corroboration -- this module is what makes that distinction visible to
confidence.py's confidence scoring and, through it, to the user.

Communication / relationships
------------------------------
- knowledge/synthesizer.py: synthesize() constructs one CitationGraph
  per answer and calls add_citation(topic, source_id) for every
  distinct source_id that ended up contributing a chosen sentence.
- brisart_ai/knowledge/confidence.py: compute_confidence() calls
  corroboration_count() when a graph is supplied, so corroboration
  from independent sources counts more than repetition from one.
- Persists to a small SQLite table via the SAME connection
  knowledge/index.py's Index already owns (init_citation_schema(index)
  mirrors knowledge/vault.py's own init_vault_schema(index) pattern:
  idempotent CREATE TABLE IF NOT EXISTS, safe to call on every
  request). No new database FILE is introduced -- this rides on the
  existing brisart_ai_index.sqlite3.

Settings / parameters
----------------------
- topic_key(topic): topics are normalized (casefolded, whitespace
  collapsed) before being used as a graph key, so "Microsoft Founders"
  and "microsoft  founders" are treated as the same topic rather than
  silently fragmenting corroboration counts across near-duplicate
  topic strings.
- MAX_RELATED_SOURCES (20): get_related_sources() caps how many
  co-cited source ids it returns, since a very broad topic string
  could otherwise accumulate an unbounded co-citation list over the
  life of an index.
- The in-memory CitationGraph class (no SQLite dependency at all) is
  provided as the primary, directly-testable data structure;
  init_citation_schema()/record_citation_sql()/corroboration_count_sql()
  are a thin SQLite-backed mirror of the same operations for
  production use, so either can be used depending on whether
  persistence across process restarts is required.

Edge cases
----------
- add_citation() is idempotent for a given (topic, source_id) pair --
  citing the same source twice for the same topic does not inflate its
  corroboration count.
- corroboration_count() for a topic with zero recorded citations
  returns 0, never raises.
- An empty/whitespace-only topic or a falsy source_id is silently
  ignored by add_citation() rather than raising, since a synthesis
  step that produced no usable topic label should not crash the
  citation-tracking step riding alongside it.

Known limitations
-----------------
- topic_key() normalizes only whitespace/case; two differently-worded
  labels for the same topic are counted as separate topics.
- The in-memory CitationGraph is per-process; use the SQL mirror
  (record_citation_sql / corroboration_count_sql) for persistence.
- Corroboration counts distinct source ids, not independence; two
  sources that copied each other still count as two.

Examples
--------
    >>> g = CitationGraph()
    >>> g.add_citation("Microsoft founders", 1); g.add_citation("microsoft  founders", 2)
    >>> g.corroboration_count("MICROSOFT FOUNDERS")
    2
    >>> g.is_single_source_topic("microsoft founders")
    False
"""
from __future__ import annotations
import re
from typing import Dict, List, Set

MAX_RELATED_SOURCES = 20

_WHITESPACE_RE = re.compile(r"\s+")


def topic_key(topic: str) -> str:
    """Normalize a topic string into a stable graph key."""
    return _WHITESPACE_RE.sub(" ", str(topic or "")).strip().casefold()


class CitationGraph:
    """In-memory topic <-> source citation graph. See module docstring
    for the SQLite-backed mirror intended for production persistence."""

    def __init__(self) -> None:
        self._topic_to_sources: Dict[str, Set[int]] = {}
        self._source_to_topics: Dict[int, Set[str]] = {}

    def add_citation(self, topic: str, source_id) -> None:
        key = topic_key(topic)
        if not key or not source_id:
            return
        self._topic_to_sources.setdefault(key, set()).add(source_id)
        self._source_to_topics.setdefault(source_id, set()).add(key)

    def corroboration_count(self, topic: str) -> int:
        """Number of DISTINCT sources ever cited for `topic`."""
        key = topic_key(topic)
        return len(self._topic_to_sources.get(key, ()))

    def get_related_sources(self, source_id, limit: int = MAX_RELATED_SOURCES) -> List:
        """Every OTHER source id that has ever been cited for at least
        one topic that `source_id` was also cited for -- i.e. sources
        that tend to corroborate the same material."""
        related: Set = set()
        for topic in self._source_to_topics.get(source_id, ()):
            related |= self._topic_to_sources.get(topic, set())
        related.discard(source_id)
        return list(related)[:limit]

    def topics_for_source(self, source_id) -> Set[str]:
        return set(self._source_to_topics.get(source_id, ()))

    def is_single_source_topic(self, topic: str) -> bool:
        """True when exactly one distinct source has ever been cited
        for `topic` -- the signal confidence.py uses to decide whether
        a "single source" caveat belongs in the answer."""
        return self.corroboration_count(topic) == 1


# ---------------------------------------------------------------------------
# SQLite-backed mirror (optional persistence layer)
# ---------------------------------------------------------------------------

def init_citation_schema(index) -> None:
    """Create the citation_graph table if it doesn't exist yet. Safe
    to call repeatedly (mirrors knowledge/vault.py's
    init_vault_schema())."""
    index.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS citation_graph (
            topic_key TEXT NOT NULL,
            source_id INTEGER NOT NULL,
            PRIMARY KEY(topic_key, source_id)
        );
        CREATE INDEX IF NOT EXISTS idx_citation_graph_topic
            ON citation_graph(topic_key);
        """
    )
    index.conn.commit()


def record_citation_sql(index, topic: str, source_id: int) -> None:
    key = topic_key(topic)
    if not key or not source_id:
        return
    init_citation_schema(index)
    with index.conn:
        index.conn.execute(
            "INSERT OR IGNORE INTO citation_graph(topic_key, source_id) VALUES(?, ?)",
            (key, int(source_id)),
        )


def corroboration_count_sql(index, topic: str) -> int:
    key = topic_key(topic)
    if not key:
        return 0
    init_citation_schema(index)
    row = index.conn.execute(
        "SELECT COUNT(DISTINCT source_id) FROM citation_graph WHERE topic_key = ?",
        (key,),
    ).fetchone()
    return int(row[0]) if row else 0


def _self_test() -> None:
    graph = CitationGraph()
    assert graph.corroboration_count("microsoft founders") == 0
    graph.add_citation("Microsoft Founders", 1)
    graph.add_citation("microsoft  founders", 2)  # normalized to same key
    graph.add_citation("Microsoft Founders", 1)  # idempotent
    assert graph.corroboration_count("MICROSOFT FOUNDERS") == 2
    assert not graph.is_single_source_topic("microsoft founders")

    graph.add_citation("Transistor History", 3)
    assert graph.is_single_source_topic("transistor history")
    assert graph.corroboration_count("transistor history") == 1

    graph.add_citation("Microsoft Founders", 3)
    related = graph.get_related_sources(1)
    assert 2 in related and 3 in related

    # ignored inputs
    graph.add_citation("", 99)
    graph.add_citation("some topic", None)
    assert graph.corroboration_count("") == 0


if __name__ == "__main__":
    _self_test()
    print("citation_graph self-test passed.")


__all__ = [
    "MAX_RELATED_SOURCES", "topic_key", "CitationGraph",
    "init_citation_schema", "record_citation_sql", "corroboration_count_sql",
]



