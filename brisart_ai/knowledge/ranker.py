"""Retrieval and ranking for BrisartAI.

Ranking model (pure Python, no dependencies):

1. Query terms are split into *meaningful* terms and *stopwords*.
   Stopwords -- ultra-common function/question words like "how", "many",
   "the", "is" -- are kept (so a query like "how many cats" still works)
   but weighted down hard, because a page that is merely dense in the
   word "many" is almost never the answer to a real question.
2. Each matching source accumulates a TF-IDF style score, with the
   stopword down-weight applied per term AND a document-length
   normalization factor applied per term (see step 2a below).
2a. Document-length normalization. A live failure surfaced a real gap
   here: a very long, broad Wikipedia article (e.g. "South Africa")
   naturally repeats common query words like "president" many times
   simply because it is long and covers a lot of ground, not because it
   is actually about the query. Raw term frequency has no way to tell
   "genuinely dense in this topic" apart from "extremely long article
   about something else that mentions this word a dozen times in
   passing". A BM25-style length-normalization factor is applied to
   each term's contribution: a document longer than the corpus average
   has its term-frequency contribution scaled down, and a document
   shorter than average has it scaled up slightly, using the
   established formula ``(1 - b) + b * (doc_len / avg_doc_len)`` for
   the divisor. This is a well-known, minimal fix (the same idea BM25
   uses) rather than a novel heuristic.
3. A *coverage* multiplier then rewards documents that match MORE of the
   distinct meaningful query terms. A dictionary page for the word
   "many" matches zero meaningful terms from "how many cats are in
   america" (cats, america) and is pushed to the bottom; a real
   cat-population page that matches both "cats" and "america" rises to
   the top. This coverage signal is what actually stops the "definition
   of many" hijack -- and, combined with length normalization above, also
   stops a long, broad article from winning on raw term mass alone.
4. A *title-match* multiplier rewards documents whose TITLE (not just
   body) contains meaningful query terms -- but each matched term's
   contribution is weighted, not counted flatly, by two independent
   signals:
     * Corpus rarity (IDF, reusing the same per-term inverse-document-
       frequency already computed during step 2's TF-IDF pass): a term
       that appears in few indexed documents contributes more than one
       that appears in many.
     * A small fixed list of generic instructional/question verbs
       (:data:`GENERIC_QUERY_VERBS` -- "explain", "describe", "define",
       etc.) is dampened outright, independent of corpus statistics.
       This second guard is necessary, not optional: in a small or
       freshly-crawled index, a generic word that happens to appear in
       only one indexed document looks exactly as "rare" by IDF as a
       genuinely specific term like a person's name -- corpus rarity
       alone cannot tell "explain" apart from "brisart" when both have
       a document frequency of 1.
4a. A *generic-concept-title* penalty demotes a document whose title (or
   URL-derived slug) is nothing more than a single bare abstract concept
   word shared with the query -- e.g. a page titled "Law" (or "Law -
   Wikipedia") for the query "what laws have been passed since trump
   became president". This reuses the fixed
   :data:`brisart_ai.intent.GENERIC_CONCEPT_TITLES` vocabulary via
   :func:`brisart_ai.intent.is_bare_generic_concept_title`, but applies
   unconditionally in this module regardless of detected intent. Without
   this, the equivalent guard embedded in :func:`brisart_ai.intent.score_intent`
   (via ``is_generic_concept_page``) was silently skipped for any query
   that does not classify into one of the five specific intents
   (founder/inventor/statistic/explanation/comparison) -- which turned
   out to be a large share of ordinary questions, including "what laws
   have been passed since trump became president" (classified
   INTENT_GENERAL).
5. A *phrase-match* multiplier rewards documents where the literal query
   text appears as a contiguous phrase, not just as scattered individual
   words. Bag-of-words scoring is blind to word order and adjacency, so
   searching for an exact note title or quoted phrase previously got no
   special credit over a document that merely contained the same words
   apart from each other.
6. An *intent* adjustment from :mod:`brisart_ai.intent` is applied last,
   for non-general intents only (see step 4a for how the general-intent
   case is separately covered). Steps 1-5 only measure whether and how a
   document mentions the query's words; they cannot tell WHY it mentions
   them. For "who invented microsoft" an imported PowerPoint manual and a
   company history both match "microsoft", and the manual can easily win
   on term frequency alone. The intent layer supplies the missing genre
   signal, boosting founder/history vocabulary and demoting
   product/account vocabulary. This is the same module the web ranker
   uses, so offline retrieval and public web search cannot drift apart.

Every stage above is deliberately explainable: title/phrase/intent/
generic-concept/length-normalization adjustments each return (or log)
the exact signal(s) that fired, so ``scripts/debug_offline_replay.py``
and ``scripts/debug_search_replay.py`` can show precisely why a document
ranked where it did rather than just a final opaque number.

1.0.0-beta.8 note: :func:`phrase_match_adjust` is now also imported
directly by ``web/crawler.py`` so public web ranking can apply the same
literal-phrase bonus to a result's URL+title text that offline ranking
already applies to a document's title/location/body. This keeps the two
ranking paths aligned rather than reimplementing the same phrase check
twice (see the ``web/crawler.py`` module docstring for the web-side
half of this change).
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

# Ultra-common English function words and question words. These are not
# dropped from the query (so short natural questions still match), but
# they contribute very little to ranking on their own.
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

# Generic instructional/question verbs that carry very little topical
# specificity even though they are meaningful enough not to belong in
# STOPWORDS (they matter for base TF-IDF/coverage scoring in a query
# like "explain the transistor" -- dropping them entirely would lose
# signal). Title-matching is the one place they cause real harm: a
# title that consists mostly of one of these words (a dictionary/
# vocabulary page defining the word itself) is not more relevant than a
# page whose title contains the actual subject being asked about.
# See title_match_adjust() for why this list exists independently of
# IDF-based corpus rarity.
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

# How much a stopword term counts relative to a meaningful term.
STOPWORD_WEIGHT = 0.15

# Coverage multiplier bounds. A document that matches none of the
# meaningful query terms keeps only COVERAGE_FLOOR of its base score; a
# document that matches all of them keeps the full score.
COVERAGE_FLOOR = 0.15

# -- document-length normalization ------------------------------------------
# BM25-style length normalization: divides each term's raw contribution
# by ``(1 - LENGTH_NORM_B) + LENGTH_NORM_B * (doc_len / avg_doc_len)``.
# LENGTH_NORM_B = 0 disables normalization entirely (score depends only
# on raw term frequency, the previous behavior); LENGTH_NORM_B = 1 fully
# normalizes by length. 0.6 is a moderate middle ground: long documents
# are meaningfully discounted for their length, but a long document that
# is genuinely dense in on-topic terms (and therefore also wins on
# coverage) is not crushed outright.
LENGTH_NORM_B = 0.6

# Document length is approximated as the sum of term frequencies indexed
# for that source (i.e. total indexed word occurrences), not raw
# character/byte count, so it is directly comparable to the term-count
# arithmetic already used elsewhere in this module.
_DOC_LENGTH_FALLBACK = 1.0

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

# Fixed damping multiplier applied to any GENERIC_QUERY_VERBS term's
# contribution to the title-match bonus, on top of (i.e. multiplied
# with) whatever IDF-based weight it would otherwise receive. 0.2 means
# a generic verb contributes at most a fifth of what an equally-rare
# specific term would contribute -- enough to not be zero (so a query
# that is genuinely about the word "explain" itself still gets some
# credit), but never enough to let it dominate over an actual subject
# term sitting in a competing document's title.
GENERIC_TERM_DAMPING = 0.2

# -- generic-concept-title penalty ------------------------------------------
# Fixed penalty multiplier applied when a document's title or URL-slug
# is nothing more than a bare abstract concept word (see the module
# docstring's step 4a and brisart_ai.intent.is_bare_generic_concept_title).
# Applied as a flat multiplier rather than a "drop the result" filter,
# consistent with the rest of this module's "intent is a hint, not a
# verdict" philosophy -- a bare concept page is still shown if nothing
# better exists, just ranked well below anything more specific.
GENERIC_CONCEPT_TITLE_PENALTY_FACTOR = 0.35
SIGNAL_GENERIC_CONCEPT_TITLE = "<generic-concept-title>"

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
    term_idf: Optional[Dict[str, float]] = None,
) -> Tuple[float, List[str]]:
    """Boost a score for meaningful query terms present in the title.

    Each matched term's contribution is weighted, not counted flatly, by
    two independent signals -- see the module docstring's step 4 for the
    full reasoning:

    * ``term_idf``, when supplied, is the per-term inverse-document-
      frequency already computed for this query during the base TF-IDF
      pass in :func:`search`. A term's weight is normalized against the
      query's own average IDF, so a rarer-than-average term contributes
      more than a more-common-than-average one.
    * :data:`GENERIC_QUERY_VERBS` applies a fixed damping multiplier
      (:data:`GENERIC_TERM_DAMPING`) on top of that, regardless of IDF.
      This is necessary because IDF alone cannot distinguish a genuinely
      rare, specific term from a generic word that merely happens to
      appear in only one document of a small or freshly-crawled index --
      both would otherwise look equally "rare".

    Returns ``(factor, boosts_hit)``. ``factor`` is 1.0 (no change) when
    the title is empty or shares no meaningful term with the query.
    """
    if not title or not meaningful_terms:
        return (1.0, [])
    title_terms = set(tokenize(title)) & meaningful_terms
    if not title_terms:
        return (1.0, [])
    if term_idf:
        average_idf = sum(term_idf.values()) / len(term_idf)
    else:
        average_idf = 1.0
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
    factor = min(
        TITLE_MATCH_MAX_FACTOR,
        1.0 + (TITLE_MATCH_WEIGHT * weighted_total),
    )
    return (
        factor,
        [f"{SIGNAL_TITLE_MATCH}:{','.join(matched_terms)}"],
    )


def generic_concept_title_adjust(
    title: str,
    location: str,
) -> Tuple[float, List[str]]:
    """Penalize a document whose title/URL is a bare generic concept.

    Checks the document's display title directly, plus every candidate
    derived from its location (the location itself and, when it looks
    like a URL, its last path segment -- see
    :func:`brisart_ai.intent.name_candidates`). This covers both an
    encyclopedia page's display title (``"Law - Wikipedia"``) and its
    URL slug (``".../wiki/Law"``), either of which alone is enough to
    identify a bare-concept page.

    Applied unconditionally, regardless of detected intent -- see the
    module docstring's step 4a for why this cannot simply rely on the
    equivalent check embedded in :func:`brisart_ai.intent.score_intent`,
    which only ever runs for the five specific intents.
    """
    candidates = [title] + name_candidates(location or "")
    for candidate in candidates:
        if is_bare_generic_concept_title(candidate):
            return (
                GENERIC_CONCEPT_TITLE_PENALTY_FACTOR,
                [SIGNAL_GENERIC_CONCEPT_TITLE],
            )
    return (1.0, [])


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
    term_idf: Optional[Dict[str, float]] = None,
) -> Tuple[float, List[str], List[str]]:
    """Apply title-match, generic-concept, phrase-match, and intent
    adjustments to a score.

    Returns ``(adjusted_score, boosts_hit, penalties_hit)``. Kept as one
    function (rather than separately-invoked ones) so
    ``scripts/debug_offline_replay.py`` and ``search()`` below can score a
    document in a single call and get back the full, explainable set of
    reasons behind its final score.

    Title-match, generic-concept, and phrase-match adjustments apply to
    every document regardless of detected intent, since they measure
    whether the document actually contains what was asked for (or is a
    bare concept page that only superficially does), not why. The
    genre-specific intent adjustment from :mod:`brisart_ai.intent` is
    skipped entirely for :data:`brisart_ai.intent.INTENT_GENERAL`,
    matching prior behavior -- but the generic-concept-title check below
    is NOT skipped for INTENT_GENERAL, which is the fix for exactly the
    gap that check used to have (see the module docstring's step 4a).

    ``term_idf``, when supplied, is threaded into :func:`title_match_adjust`
    so title-match weighting reuses the same per-term corpus rarity
    already computed once for base TF-IDF scoring in :func:`search`.

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
    title_factor, title_boosts = title_match_adjust(
        title, topic_terms or set(), term_idf
    )
    if title_factor != 1.0:
        score *= title_factor
        boosts.extend(title_boosts)
    generic_factor, generic_penalties = generic_concept_title_adjust(
        title, location
    )
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


def _build_doc_length_sql(source_types: Optional[Iterable[str]], source_type: Optional[str]) -> str:
    """Build the per-source document-length aggregate query.

    Document length is approximated as the sum of indexed term
    frequencies for a source (i.e. total indexed word occurrences),
    which is directly comparable to the tf/idf arithmetic already used
    elsewhere in this module without needing an extra stored column.
    """
    if source_types:
        placeholders = ",".join(["?"] * len(source_types))
        return f"""
            SELECT
                terms.source_id,
                SUM(terms.tf) AS total_terms
            FROM terms
            JOIN sources
                ON sources.id = terms.source_id
            WHERE sources.source_type IN ({placeholders})
            GROUP BY terms.source_id
        """
    if source_type:
        return """
            SELECT
                terms.source_id,
                SUM(terms.tf) AS total_terms
            FROM terms
            JOIN sources
                ON sources.id = terms.source_id
            WHERE sources.source_type = ?
            GROUP BY terms.source_id
        """
    return """
        SELECT source_id, SUM(tf) AS total_terms
        FROM terms
        GROUP BY source_id
    """


def _load_document_lengths(
    index,
    types_list: Optional[List[str]],
    source_type: Optional[str],
) -> Tuple[Dict[int, float], float]:
    """Return (per-source document length, corpus average length).

    Lengths are computed once per query via a single aggregate query
    (see :func:`_build_doc_length_sql`), scoped to the same source-type
    filter as the rest of the search, so the average is meaningful for
    the corpus actually being searched (e.g. only "file" sources when
    the caller restricts to local files).
    """
    doc_length_sql = _build_doc_length_sql(types_list, source_type)
    if types_list:
        rows = index.conn.execute(doc_length_sql, tuple(types_list)).fetchall()
    elif source_type:
        rows = index.conn.execute(doc_length_sql, (source_type,)).fetchall()
    else:
        rows = index.conn.execute(doc_length_sql).fetchall()
    lengths: Dict[int, float] = {
        source_id: float(total_terms or 0)
        for source_id, total_terms in rows
    }
    if lengths:
        average_length = sum(lengths.values()) / len(lengths)
    else:
        average_length = _DOC_LENGTH_FALLBACK
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
    # Document lengths, for the BM25-style length-normalization factor
    # applied to each term's contribution below. Computed once up front
    # via a single aggregate query rather than per-term, since the same
    # lengths apply across every term in this search.
    doc_lengths, average_doc_length = _load_document_lengths(
        index, types_list, source_type
    )
    scores: Dict[int, float] = collections.defaultdict(float)
    # Track which distinct meaningful terms each source matched, so we
    # can reward broad topical coverage rather than raw repetition of a
    # single common word.
    matched_meaningful: Dict[int, Set[str]] = collections.defaultdict(set)
    # Per-term inverse-document-frequency, captured here so title-match
    # weighting (see title_match_adjust()) can reuse the exact same
    # corpus-rarity signal already computed for base TF-IDF scoring,
    # instead of recomputing it or -- worse -- not having it at all.
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
        inverse_document_frequency = (
            math.log(
                (total_sources + 1)
                / (document_frequency + 1)
            )
            + 1.0
        )
        term_idf[term] = inverse_document_frequency
        weight = _term_weight(term)
        is_meaningful = term not in STOPWORDS
        for source_id, term_frequency in rows:
            adjusted_frequency = (
                1.0 + math.log(max(1, term_frequency))
            )
            doc_length = doc_lengths.get(source_id, average_doc_length)
            length_norm = (1.0 - LENGTH_NORM_B) + LENGTH_NORM_B * (
                doc_length / average_doc_length
            )
            if length_norm <= 0:
                length_norm = 1.0
            scores[source_id] += (
                weight
                * (adjusted_frequency / length_norm)
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
    # Relevance-adjustment pass (title match, generic-concept, phrase
    # match, intent). Every candidate is fetched before the final sort,
    # because these signals live in the title and body text rather than
    # in the term table. Only a bounded candidate pool is considered --
    # adjusting the whole index would mean reading every row on every
    # query.
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
            term_idf=term_idf,
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
    "GENERIC_CONCEPT_TITLE_PENALTY_FACTOR",
    "GENERIC_QUERY_VERBS",
    "GENERIC_TERM_DAMPING",
    "INTENT_MAX_FACTOR",
    "INTENT_MIN_FACTOR",
    "INTENT_TEXT_CHARS",
    "INTENT_WEIGHT",
    "LENGTH_NORM_B",
    "PHRASE_MATCH_FACTOR",
    "PHRASE_MATCH_MIN_WORDS",
    "SIGNAL_GENERIC_CONCEPT_TITLE",
    "SIGNAL_PHRASE_MATCH",
    "SIGNAL_TITLE_MATCH",
    "STOPWORDS",
    "TITLE_MATCH_MAX_FACTOR",
    "TITLE_MATCH_WEIGHT",
    "generic_concept_title_adjust",
    "intent_adjust",
    "phrase_match_adjust",
    "search",
    "title_match_adjust",
]
