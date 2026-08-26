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
4. A *title-match* multiplier rewards documents whose TITLE (not just
   body) contains meaningful query terms. Plain TF-IDF treats every
   occurrence of a term identically regardless of field, so a term
   appearing once in a short, on-topic title counted for no more than
   the same term buried once in a huge, mostly-unrelated body. A title
   match is much stronger evidence of relevance and is now rewarded
   explicitly.
5. A *phrase-match* multiplier rewards documents where the literal query
   text appears as a contiguous phrase, not just as scattered individual
   words. Bag-of-words scoring is blind to word order and adjacency, so
   searching for an exact note title or quoted phrase previously got no
   special credit over a document that merely contained the same words
   apart from each other.
6. An *intent* adjustment from :mod:`brisart_ai.intent` is applied last.
   Steps 1-5 only measure whether and how a document mentions the
   query's words; they cannot tell WHY it mentions them. For "who
   invented microsoft" an imported PowerPoint manual and a company
   history both match "microsoft", and the manual can easily win on
   term frequency alone. The intent layer supplies the missing genre
   signal, boosting founder/history vocabulary and demoting
   product/account vocabulary. This is the same module the web ranker
   uses, so offline retrieval and public web search cannot drift apart.
   That mattered here: three copies of the dictionary blocklist had
   already rotted independently before being consolidated, and
   duplicating intent rules would repeat that.

Every stage above is deliberately explainable: title/phrase/intent
adjustments each return the exact signal(s) that fired, so
``scripts/debug_offline_replay.py`` and ``scripts/debug_search_replay.py``
can show precisely why a document ranked where it did rather than just a
final opaque number.
"""
from __future__ import annotations

import collections
import math
import re
from typing import Dict, Iterable, List, Optional, Set, Tuple

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

# -- title-match bonus ------------------------------------------------------
# Bonus per distinct meaningful query term found in the document's own
# title, on top of whatever that term already contributed via ordinary
# TF-IDF scoring. A title match is materially stronger evidence of
# relevance than the same word appearing once somewhere inside a long
# body, and previously nothing in the model distinguished the two.
TITLE_MATCH_WEIGHT = 0.12
TITLE_MATCH_MAX_FACTOR = 1.42
SIGNAL_TITLE_MATCH = "<title-match>"

# -- phrase-match bonus -------------------------------------------------------
# Flat multiplier applied when the literal query text appears as a
# contiguous phrase somewhere in the title, location, or body. Bag-of-words
# scoring cannot see word order or adjacency, so a search for an exact
# note title or quoted phrase previously got no more credit than a
# document containing the same words scattered far apart. Only applied to
# genuinely multi-word queries -- a single meaningful word already gets
# full credit from ordinary term scoring, so treating it as a "phrase"
# here would just double-count it.
PHRASE_MATCH_FACTOR = 1.35
PHRASE_MATCH_MIN_WORDS = 2
SIGNAL_PHRASE_MATCH = "<phrase-match>"

_PHRASE_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _normalize_for_phrase(text: str) -> str:
    """Collapse punctuation/case so phrase matching is format-agnostic."""
    return _PHRASE_NORMALIZE_RE.sub(" ", str(text or "").casefold()).strip()


def _term_weight(term: str) -> float:
    """Return the ranking weight for a single query term."""
    return STOPWORD_WEIGHT if term in STOPWORDS else 1.0


def title_match_adjust(
    title: str,
    meaningful_terms: Set[str],
) -> Tuple[float, List[str]]:
    """Boost a score for meaningful query terms present in the title.

    Returns ``(factor, boosts_hit)``. ``factor`` is 1.0 (no change) when
    the title is empty or shares no meaningful term with the query.
    """
    if not title or not meaningful_terms:
        return (1.0, [])
    title_terms = set(tokenize(title)) & meaningful_terms
    if not title_terms:
        return (1.0, [])
    factor = min(
        TITLE_MATCH_MAX_FACTOR,
        1.0 + (TITLE_MATCH_WEIGHT * len(title_terms)),
    )
    return (factor, [f"{SIGNAL_TITLE_MATCH}:{len(title_terms)}"])


def phrase_match_adjust(
    query: str,
    haystack: str,
) -> Tuple[float, List[str]]:
    """Boost a score when the literal query phrase appears verbatim.

    Returns ``(factor, boosts_hit)``. Only fires for queries with at
    least :data:`PHRASE_MATCH_MIN_WORDS` words, since a single-word query
    already receives full credit through ordinary term scoring.
    """
    normalized_query = _normalize_for_phrase(query)
    if len(normalized_query.split()) < PHRASE_MATCH_MIN_WORDS:
        return (1.0, [])
    normalized_haystack = _normalize_for_phrase(haystack)
    if normalized_query and normalized_query in normalized_haystack:
        return (PHRASE_MATCH_FACTOR, [SIGNAL_PHRASE_MATCH])
    return (1.0, [])


def intent_adjust(
    base_score: float,
    title: str,
    text: str,
    location: str,
    intent: str,
    query: str,
    topic_terms: Optional[Set[str]] = None,
) -> Tuple[float, List[str], List[str]]:
    """Apply title-match, phrase-match, and intent adjustments to a score.

    Returns ``(adjusted_score, boosts_hit, penalties_hit)``. Kept as one
    function (rather than three separately-invoked ones) so
    ``scripts/debug_offline_replay.py`` and ``search()`` below can score a
    document in a single call and get back the full, explainable set of
    reasons -- title match, phrase match, and intent -- behind its final
    score.

    Title-match and phrase-match adjustments apply to every document
    regardless of detected intent, since they measure whether the
    document actually contains what was asked for, not why. The intent
    adjustment is skipped entirely for :data:`brisart_ai.intent.INTENT_GENERAL`,
    matching prior behavior.

    Title, location, and a bounded prefix of the body are combined into
    one haystack for phrase and intent matching: the title states the
    genre, the location often repeats it, and the body holds the
    concrete evidence (named founders, a year, a figure).
    """
    haystack = " ".join(
        part
        for part in (
            str(title or ""),
            str(location or ""),
            str(text or "")[:INTENT_TEXT_CHARS],
        )
        if part
    )

    score = base_score
    boosts: List[str] = []
    penalties: List[str] = []

    title_factor, title_boosts = title_match_adjust(title, topic_terms or set())
    if title_factor != 1.0:
        score *= title_factor
        boosts.extend(title_boosts)

    phrase_factor, phrase_boosts = phrase_match_adjust(query, haystack)
    if phrase_factor != 1.0:
        score *= phrase_factor
        boosts.extend(phrase_boosts)

    if intent == INTENT_GENERAL:
        return (score, boosts, penalties)

    delta, intent_boosts, intent_penalties = score_intent(
        haystack,
        intent,
        query,
        topic_terms=topic_terms,
    )
    factor = 1.0 + (delta * INTENT_WEIGHT)
    factor = max(INTENT_MIN_FACTOR, min(INTENT_MAX_FACTOR, factor))
    score *= factor
    boosts.extend(intent_boosts)
    penalties.extend(intent_penalties)
    return (score, boosts, penalties)


def _build_term_sql(source_types: Optional[Iterable[str]], source_type: Optional[str]) -> str:
    """Build the per-term lookup SQL for the requested source scoping.

    Exactly one of ``source_types`` (an IN-clause allow-list) or
    ``source_type`` (a single exact match, kept for backward
    compatibility with older call sites) should be supplied; if both are
    empty, every indexed source type is searched.
    """
    if source_types:
        placeholders = ",".join(["?"] * len(source_types))
        return f"""
            SELECT
                terms.source_id,
                terms.tf
            FROM terms
            JOIN sources
                ON sources.id = terms.source_id
            WHERE terms.term = ?
              AND sources.source_type IN ({placeholders})
        """
    if source_type:
        return """
            SELECT
                terms.source_id,
                terms.tf
            FROM terms
            JOIN sources
                ON sources.id = terms.source_id
            WHERE terms.term = ?
              AND sources.source_type = ?
        """
    return """
        SELECT source_id, tf
        FROM terms
        WHERE term = ?
    """


def search(
    index,
    query: str,
    limit: int = 8,
    source_type: Optional[str] = None,
    source_types: Optional[Iterable[str]] = None,
) -> List[Dict[str, object]]:
    """Search indexed sources and rank matches by term relevance.

    ``source_type`` restricts the search to a single exact source type
    (e.g. ``"web"``), matching prior behavior. ``source_types`` instead
    accepts any iterable of allowed types (e.g. ``{"file", "web",
    "note"}``) and searches the union of them; this is what
    ``core/conversation.py`` uses to combine the Local Files and Research
    Notes settings toggles into a single ranked query instead of running
    a separate, less-capable search for notes. If neither is supplied,
    every indexed source type is searched.
    """
    terms = tokenize(query)
    if not terms:
        return []
    unique_terms = set(terms)
    meaningful_terms = {
        term for term in unique_terms if term not in STOPWORDS
    }
    meaningful_total = len(meaningful_terms)

    types_list = list(source_types) if source_types else None
    if types_list:
        total_sources = max(1, sum(index.source_count(t) for t in types_list))
    elif source_type:
        total_sources = max(1, index.source_count(source_type))
    else:
        total_sources = max(1, index.source_count())

    term_sql = _build_term_sql(types_list, source_type)

    scores: Dict[int, float] = collections.defaultdict(float)
    # Track which distinct meaningful terms each source matched, so we
    # can reward broad topical coverage rather than raw repetition of a
    # single common word.
    matched_meaningful: Dict[int, Set[str]] = collections.defaultdict(set)
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
    # Relevance-adjustment pass (title match, phrase match, intent).
    # Every candidate is fetched before the final sort, because these
    # signals live in the title and body text rather than in the term
    # table. Only a bounded candidate pool is considered -- adjusting the
    # whole index would mean reading every row on every query.
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
    "PHRASE_MATCH_FACTOR",
    "PHRASE_MATCH_MIN_WORDS",
    "SIGNAL_PHRASE_MATCH",
    "SIGNAL_TITLE_MATCH",
    "STOPWORDS",
    "TITLE_MATCH_MAX_FACTOR",
    "TITLE_MATCH_WEIGHT",
    "intent_adjust",
    "phrase_match_adjust",
    "search",
    "title_match_adjust",
]
