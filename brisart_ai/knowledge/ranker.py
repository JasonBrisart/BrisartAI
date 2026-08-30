"""brisart_ai/knowledge/ranker.py

Retrieval and ranking over BrisartAI's local index -- pure-Python
TF-IDF layered with five extra signals, because "matches the query's
words" and "actually answers the query" are not the same thing.

**The base score.** Query terms split into meaningful terms and
stopwords. Stopwords (ultra-common function/question words like "how,"
"many," "the") are kept -- so "how many cats" still works -- but
weighted at 15% of an ordinary term, because a page merely dense in the
word "many" is almost never the answer to a real question. Each term's
contribution is also normalized by document length, BM25-style: a
document longer than the corpus average has its term-frequency
contribution scaled down, which stops a very long, broad article from
winning purely because it's long enough to mention every query word in
passing somewhere.

**Coverage.** A document matching more of the DISTINCT meaningful query
terms gets multiplied up (floor 0.15x for zero matches, up to 1.0x for
matching everything). This is what actually stops a page dense in one
common word from beating a genuine multi-term match.

**Title match.** A document whose own title contains meaningful query
terms gets boosted, weighted by how rare that term is across the corpus
(IDF) and specifically DAMPED for a fixed list of generic instructional
verbs (`explain`, `describe`, `define`, ...) via `GENERIC_QUERY_VERBS` --
IDF alone can't tell a genuinely rare, specific term from a generic word
that merely happens to appear in only one document of a small or
freshly-crawled index; both look equally "rare" to IDF alone.

**Generic-concept-title penalty.** A document titled nothing but a bare
abstract concept word shared with the query (a page titled "Law" for a
question about specific legislation) gets demoted, unconditionally --
regardless of detected intent. This has to be a standalone check
(`generic_concept_title_adjust()`) rather than relying solely on the
equivalent guard inside `brisart_ai.intent.score_intent()`, because that
function is never even called for `INTENT_GENERAL` queries.

**Phrase match.** A document where the literal query text appears as a
contiguous phrase (not just scattered words) gets a flat multiplier.

**Intent.** Last, for non-general intents only, `brisart_ai.intent`
supplies the "why does this document mention the query's words" signal
none of the above can provide.

Every one of these stages returns the exact signal(s) that fired, so
scripts/debug_offline_replay.py can show precisely why a document
ranked where it did instead of an opaque final number.
"""
from __future__ import annotations

import collections
import math
import re
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from brisart_ai.intent import (
    INTENT_GENERAL,
    detect_intent,
    is_bare_generic_concept_title,
    name_candidates,
    score_intent,
)
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

# Generic instructional/question verbs -- meaningful enough for base
# TF-IDF/coverage scoring ("explain the transistor" needs "explain" to
# count for something) but title-matching is where they cause real
# harm: a dictionary page titled mostly "Define" is not more relevant
# than one titled with the actual subject.
GENERIC_QUERY_VERBS: Set[str] = {
    "explain", "explains", "explained", "explanation",
    "describe", "describes", "described", "description",
    "define", "defines", "defined", "definition",
    "meaning", "meanings",
    "tell", "tells", "give", "gives",
    "summarize", "summarizes", "summarise", "summarises",
    "outline", "outlines", "elaborate", "elaborates",
    "clarify", "clarifies", "understand", "understands",
    "know", "knows", "find", "finds", "show", "shows",
    "list", "lists",
}

STOPWORD_WEIGHT = 0.15
COVERAGE_FLOOR = 0.15

# BM25-style length normalization strength. 0 disables it entirely
# (score depends only on raw term frequency); 1 fully normalizes. 0.6 is
# a moderate middle: long documents are meaningfully discounted, but one
# that's genuinely dense in on-topic terms (and therefore already wins
# on coverage) isn't crushed outright. Document length is approximated
# as the sum of indexed term frequencies for that source, not raw
# byte/char count, so it's directly comparable to the tf/idf arithmetic
# used elsewhere in this module.
LENGTH_NORM_B = 0.6
_DOC_LENGTH_FALLBACK = 1.0

# Weight of one intent point, as a fraction of a document's own base
# score rather than a flat constant -- TF-IDF scores have no fixed
# scale, so a flat bonus would be decisive in a small index and
# negligible in a large one. Clamped so a document can lose at most 60%
# of its score or gain at most 90% for genre fit: intent is a hint, not
# a verdict.
INTENT_WEIGHT = 0.30
INTENT_MIN_FACTOR = 0.40
INTENT_MAX_FACTOR = 1.90

# How much body text feeds the intent check -- the title carries the
# clearest signal, but the body is where "founded by Bill Gates" or "an
# estimated 73.8 million pet cats" actually lives.
INTENT_TEXT_CHARS = 2000

# Size of the candidate pool that gets the (relatively expensive) title/
# phrase/intent pass, as a multiple of the requested limit plus a floor.
# Scoring the entire index on every query would mean reading every row;
# a pool several times the limit is enough for a genuinely better
# document to climb into the results without that cost.
INTENT_CANDIDATE_FACTOR = 5
INTENT_CANDIDATE_MIN = 10

# Title-match bonus strength/cap, and the damping applied to
# GENERIC_QUERY_VERBS within it. 0.2 means a generic verb contributes at
# most a fifth of what an equally-rare specific term would -- enough
# that a query genuinely about the word "explain" still gets some
# credit, never enough to dominate over a real subject term.
TITLE_MATCH_WEIGHT = 0.12
TITLE_MATCH_MAX_FACTOR = 1.42
GENERIC_TERM_DAMPING = 0.2
SIGNAL_TITLE_MATCH = "<title-match>"

# Flat multiplier for a document whose title/URL-slug is nothing but a
# bare generic-concept word -- still shown if nothing better exists,
# just ranked well below anything more specific.
GENERIC_CONCEPT_TITLE_PENALTY_FACTOR = 0.35
SIGNAL_GENERIC_CONCEPT_TITLE = "<generic-concept-title>"

# Only applied to genuinely multi-word queries -- a single meaningful
# word already gets full credit from ordinary term scoring, so treating
# it as a "phrase" here would just double-count it.
PHRASE_MATCH_FACTOR = 1.35
PHRASE_MATCH_MIN_WORDS = 2
SIGNAL_PHRASE_MATCH = "<phrase-match>"

_PHRASE_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _normalize_for_phrase(text: str) -> str:
    """Collapse punctuation/case so phrase matching is format-agnostic."""
    return _PHRASE_NORMALIZE_RE.sub(" ", str(text or "").casefold()).strip()


def _term_weight(term: str) -> float:
    return STOPWORD_WEIGHT if term in STOPWORDS else 1.0


def title_match_adjust(
    title: str,
    meaningful_terms: Set[str],
    term_idf: Optional[Dict[str, float]] = None,
) -> Tuple[float, List[str]]:
    """Boost a score for meaningful query terms present in the title.

    Each matched term's weight combines two signals: `term_idf` (this
    query's own already-computed per-term rarity, normalized against the
    query's average IDF) and a fixed damping multiplier for
    GENERIC_QUERY_VERBS on top of that -- IDF alone can't distinguish a
    genuinely rare specific term from a generic word that merely happens
    to appear in only one document of a small index. Returns `(1.0, [])`
    unchanged for an empty title or one sharing no meaningful term.
    """
    if not title or not meaningful_terms:
        return (1.0, [])

    title_terms = set(tokenize(title)) & meaningful_terms
    if not title_terms:
        return (1.0, [])

    average_idf = (sum(term_idf.values()) / len(term_idf)) if term_idf else 1.0
    if average_idf <= 0:
        average_idf = 1.0

    weighted_total = 0.0
    matched_terms: List[str] = []
    for term in sorted(title_terms):
        relative_weight = 1.0
        if term_idf:
            relative_weight = term_idf.get(term, average_idf) / average_idf
        if term in GENERIC_QUERY_VERBS:
            relative_weight *= GENERIC_TERM_DAMPING
        weighted_total += relative_weight
        matched_terms.append(term)

    factor = min(TITLE_MATCH_MAX_FACTOR, 1.0 + (TITLE_MATCH_WEIGHT * weighted_total))
    return (factor, [f"{SIGNAL_TITLE_MATCH}:{','.join(matched_terms)}"])


def generic_concept_title_adjust(title: str, location: str) -> Tuple[float, List[str]]:
    """Penalize a document whose title/URL is a bare generic concept.

    Checks the display title AND every candidate derived from the
    location (the location itself, plus its last path segment if it
    looks like a URL) -- covering both an encyclopedia page's display
    title ("Law - Wikipedia") and its URL slug (".../wiki/Law"). Applied
    unconditionally regardless of detected intent, unlike the equivalent
    check embedded in brisart_ai.intent.score_intent(), which only ever
    runs for the five specific intents.
    """
    candidates = [title] + name_candidates(location or "")
    for candidate in candidates:
        if is_bare_generic_concept_title(candidate):
            return (GENERIC_CONCEPT_TITLE_PENALTY_FACTOR, [SIGNAL_GENERIC_CONCEPT_TITLE])
    return (1.0, [])


def phrase_match_adjust(query: str, haystack: str) -> Tuple[float, List[str]]:
    """Boost a score when the literal query phrase appears verbatim.

    Only fires for queries with at least PHRASE_MATCH_MIN_WORDS words --
    a single-word query already gets full credit through ordinary term
    scoring.
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
    term_idf: Optional[Dict[str, float]] = None,
) -> Tuple[float, List[str], List[str]]:
    """Apply title-match, generic-concept, phrase-match, and intent adjustments.

    Returns `(adjusted_score, boosts_hit, penalties_hit)`. Title-match,
    generic-concept, and phrase-match apply to every document regardless
    of detected intent, since they measure whether the document actually
    contains what was asked for -- not why. The genre-specific intent
    adjustment is skipped for INTENT_GENERAL, but the generic-concept-
    title check below is NOT skipped for INTENT_GENERAL, which is
    exactly the gap that check needed to close (see the module
    docstring).

    Title, location, and a bounded prefix of the body are combined into
    one haystack: the title states the genre, the location often
    repeats it, and the body holds the concrete evidence (named
    founders, a year, a figure).
    """
    haystack = " ".join(
        part for part in (
            str(title or ""), str(location or ""), str(text or "")[:INTENT_TEXT_CHARS],
        ) if part
    )

    score = base_score
    boosts: List[str] = []
    penalties: List[str] = []

    title_factor, title_boosts = title_match_adjust(title, topic_terms or set(), term_idf)
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

    if intent == INTENT_GENERAL:
        return (score, boosts, penalties)

    delta, intent_boosts, intent_penalties = score_intent(
        haystack, intent, query, topic_terms=topic_terms,
    )
    factor = 1.0 + (delta * INTENT_WEIGHT)
    factor = max(INTENT_MIN_FACTOR, min(INTENT_MAX_FACTOR, factor))
    score *= factor
    boosts.extend(intent_boosts)
    penalties.extend(intent_penalties)

    return (score, boosts, penalties)


def _build_term_sql(source_types: Optional[Iterable[str]], source_type: Optional[str]) -> str:
    """Per-term lookup SQL for the requested source scoping.

    Exactly one of source_types (an allow-list) or source_type (a
    single exact match, kept for older callers) should be supplied; if
    both are empty, every source type is searched.
    """
    if source_types:
        placeholders = ",".join(["?"] * len(source_types))
        return f"""
            SELECT terms.source_id, terms.tf
            FROM terms
            JOIN sources ON sources.id = terms.source_id
            WHERE terms.term = ? AND sources.source_type IN ({placeholders})
        """
    if source_type:
        return """
            SELECT terms.source_id, terms.tf
            FROM terms
            JOIN sources ON sources.id = terms.source_id
            WHERE terms.term = ? AND sources.source_type = ?
        """
    return "SELECT source_id, tf FROM terms WHERE term = ?"


def _build_doc_length_sql(source_types: Optional[Iterable[str]], source_type: Optional[str]) -> str:
    """Per-source document-length aggregate (sum of indexed term frequencies)."""
    if source_types:
        placeholders = ",".join(["?"] * len(source_types))
        return f"""
            SELECT terms.source_id, SUM(terms.tf) AS total_terms
            FROM terms
            JOIN sources ON sources.id = terms.source_id
            WHERE sources.source_type IN ({placeholders})
            GROUP BY terms.source_id
        """
    if source_type:
        return """
            SELECT terms.source_id, SUM(terms.tf) AS total_terms
            FROM terms
            JOIN sources ON sources.id = terms.source_id
            WHERE sources.source_type = ?
            GROUP BY terms.source_id
        """
    return "SELECT source_id, SUM(tf) AS total_terms FROM terms GROUP BY source_id"


def _load_document_lengths(
    index, types_list: Optional[List[str]], source_type: Optional[str],
) -> Tuple[Dict[int, float], float]:
    """(per-source document length, corpus average), scoped to the same filter as the search."""
    doc_length_sql = _build_doc_length_sql(types_list, source_type)
    if types_list:
        rows = index.conn.execute(doc_length_sql, tuple(types_list)).fetchall()
    elif source_type:
        rows = index.conn.execute(doc_length_sql, (source_type,)).fetchall()
    else:
        rows = index.conn.execute(doc_length_sql).fetchall()

    lengths: Dict[int, float] = {sid: float(total or 0) for sid, total in rows}
    average_length = (sum(lengths.values()) / len(lengths)) if lengths else _DOC_LENGTH_FALLBACK
    if average_length <= 0:
        average_length = _DOC_LENGTH_FALLBACK
    return lengths, average_length


def search(
    index,
    query: str,
    limit: int = 8,
    source_type: Optional[str] = None,
    source_types: Optional[Iterable[str]] = None,
) -> List[Dict[str, object]]:
    """Search indexed sources and rank matches by relevance.

    `source_type` restricts to a single exact type (e.g. "web");
    `source_types` accepts any iterable of allowed types (e.g.
    {"file", "web", "note"}) and searches their union -- what
    core/conversation.py uses to combine the Local Files and Research
    Notes toggles into one ranked query. If neither is given, every
    source type is searched.
    """
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
    term_idf: Dict[str, float] = {}

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

        inverse_document_frequency = math.log((total_sources + 1) / (document_frequency + 1)) + 1.0
        term_idf[term] = inverse_document_frequency

        weight = _term_weight(term)
        is_meaningful = term not in STOPWORDS

        for source_id, term_frequency in rows:
            adjusted_frequency = 1.0 + math.log(max(1, term_frequency))
            doc_length = doc_lengths.get(source_id, average_doc_length)
            length_norm = (1.0 - LENGTH_NORM_B) + LENGTH_NORM_B * (doc_length / average_doc_length)
            if length_norm <= 0:
                length_norm = 1.0

            scores[source_id] += weight * (adjusted_frequency / length_norm) * inverse_document_frequency
            if is_meaningful:
                matched_meaningful[source_id].add(term)

    if not scores:
        return []

    adjusted_scores: Dict[int, float] = {}
    for source_id, base_score in scores.items():
        coverage = (
            len(matched_meaningful[source_id]) / meaningful_total
            if meaningful_total > 0
            else 1.0  # query was entirely stopwords; nothing to discriminate on
        )
        multiplier = COVERAGE_FLOOR + (1.0 - COVERAGE_FLOOR) * coverage
        adjusted_scores[source_id] = base_score * multiplier

    # Relevance-adjustment pass (title/generic-concept/phrase/intent),
    # bounded to a candidate pool since it requires fetching each row's
    # title/body text.
    intent = detect_intent(query)
    candidate_pool = sorted(
        adjusted_scores.items(), key=lambda item: item[1], reverse=True
    )[: max(0, limit) * INTENT_CANDIDATE_FACTOR + INTENT_CANDIDATE_MIN]

    rows_by_id: Dict[int, tuple] = {}
    reasons: Dict[int, Tuple[List[str], List[str]]] = {}

    for source_id, base_score in candidate_pool:
        row = index.conn.execute(
            """
            SELECT source_type, location, title, text, extension, size_bytes, indexed_at
            FROM sources WHERE id = ?
            """,
            (source_id,),
        ).fetchone()
        if row is None:
            continue
        rows_by_id[source_id] = row

        new_score, boosts, penalties = intent_adjust(
            base_score, row[2] or row[1], row[3], row[1], intent, query,
            topic_terms=meaningful_terms, term_idf=term_idf,
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
    "COVERAGE_FLOOR", "GENERIC_CONCEPT_TITLE_PENALTY_FACTOR",
    "GENERIC_QUERY_VERBS", "GENERIC_TERM_DAMPING", "INTENT_MAX_FACTOR",
    "INTENT_MIN_FACTOR", "INTENT_TEXT_CHARS", "INTENT_WEIGHT",
    "LENGTH_NORM_B", "PHRASE_MATCH_FACTOR", "PHRASE_MATCH_MIN_WORDS",
    "SIGNAL_GENERIC_CONCEPT_TITLE", "SIGNAL_PHRASE_MATCH",
    "SIGNAL_TITLE_MATCH", "STOPWORDS", "TITLE_MATCH_MAX_FACTOR",
    "TITLE_MATCH_WEIGHT", "generic_concept_title_adjust", "intent_adjust",
    "phrase_match_adjust", "search", "title_match_adjust",
]
