"""Public web crawling and ingestion for BrisartAI.

This module is the single chokepoint through which every web page must
pass to be indexed.

Three layers keep junk out of your answers:

1. QUERY NORMALIZATION: a question keeps its natural phrasing when sent
   to a search engine ("how many cats are in america" is searched as
   written), because that phrasing is what matches pages containing the
   actual answer. A keyword-only form is kept as a fallback for when the
   phrased question returns nothing usable.
2. OFF-TOPIC WIKI REJECTION: a Wikipedia page whose title is itself a
   bare function word (e.g. /wiki/Many, the disambiguation page for the
   word "many") is rejected -- it is about the word, not your topic.
3. HOST BLOCKING: known dictionary/thesaurus/definition sites are
   refused at ingest time as a final safety net.

The blocklist, function-word list, and junk-detection helpers live in
brisart_ai/blocklist.py so search.py, crawler.py, and index.py all share
one definition instead of each keeping their own copy.
"""

from __future__ import annotations

import queue
import re
import time
import urllib.parse
from typing import List, Sequence, Set, Tuple

from brisart_ai.blocklist import (
    ACCOUNT_HOST_PREFIXES,
    FUNCTION_WORDS,
    LISTING_PATH_MARKERS,
    LOW_VALUE_HOSTS,
    is_junk_web_source,
)
from brisart_ai.util import (
    normalize_url,
    same_site,
    stable_hash,
)
from brisart_ai.web.fetcher import fetch_url
from brisart_ai.web.search import search_public_web
from brisart_ai.web.policy import RobotsCache
from brisart_ai.web.stats import CrawlStats

DEFAULT_DELAY_SECONDS = 1.0

# Question-intent phrases mapped to a helpful search keyword. When the
# phrase appears in the question, the keyword is appended to the search
# so results lean toward the right KIND of answer (a quantity, a price,
# a date) rather than just the topic. Longer phrases are listed first so
# the most specific intent wins.
_INTENT_HINTS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("how", "many"), "number"),
    (("how", "much"), "amount"),
    (("how", "old"), "age"),
    (("how", "tall"), "height"),
    (("how", "long"), "length duration"),
    (("how", "far"), "distance"),
    (("population", "of"), "population"),
)

_QUERY_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-']*")

# URL tokenizer. Deliberately different from _QUERY_WORD: inside a URL,
# "-", "_" and "." separate words, so "history-of-microsoft-1975" must
# tokenize to {history, of, microsoft, 1975}. Using _QUERY_WORD here was a
# real bug -- it kept the slug as ONE token, so "microsoft" never matched
# and genuine articles were scored as unrelated.
_URL_WORD = re.compile(r"[A-Za-z0-9]+")

# Longest-first so "ation" is tried before "ed"/"s".
_STEM_SUFFIXES = (
    "ations", "ation", "ings", "ing", "ors", "or", "ers", "er",
    "ions", "ion", "ed", "es", "s",
)


def _stem(word: str) -> str:
    """Crude suffix stripper so query and URL word forms can meet.

    "who invented the transistor" should match a page about the
    "Invention" of it; plain "s"-stripping missed that entirely. Kept
    deliberately shallow (no dictionary, no rewrites) and floored at 4
    characters so short words are never mangled into noise.
    """
    word = word.casefold()
    for suffix in _STEM_SUFFIXES:
        # Plural "s"/"es" needs a 3-char floor, not 4: "cats" -> "cat" is
        # exactly the case this has to handle (matching /wiki/Cat_behavior).
        # Everything else keeps the 4-char floor.
        floor = 3 if suffix in ("s", "es") else 4
        if len(word) - len(suffix) >= floor and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def clean_search_query(query: str) -> str:
    """Normalize a question for web search, keeping its natural phrasing.

    Search engines rank full natural-language questions well, because the
    question's phrasing matches the pages that actually answer it.
    Stripping a question down to bare keywords ("how many cats are in
    america" -> "cats america number") throws that signal away and
    returns pages merely *about* the topic instead of pages that answer
    it.

    So the question is passed through essentially intact: whitespace is
    normalized and trailing punctuation is dropped.

    Dictionary-definition hijacking is not prevented here (the old
    rationale for stripping "many"); it is handled where it belongs, by
    the shared blocklist in brisart_ai/blocklist.py at ingest time.
    """
    raw = str(query or "")
    normalized = " ".join(raw.split())
    stripped = normalized.strip().strip("?!.,;:").strip()
    return stripped or normalized


def search_keyword_fallback(query: str) -> str:
    """Keyword-only form of a question, used as a secondary attempt.

    Question words are removed and an intent keyword appended, e.g.
    "how many cats are in america" -> "cats america number". This is a
    fallback tried only when the natural-language query returns nothing
    usable, since it finds topical pages but not necessarily answering
    ones.
    """
    raw = str(query or "")
    lowered = " " + " ".join(raw.lower().split()) + " "

    hints: List[str] = []
    for phrase, hint in _INTENT_HINTS:
        needle = " " + " ".join(phrase) + " "
        if needle in lowered:
            hints.append(hint)

    tokens = _QUERY_WORD.findall(raw)
    kept = [
        token
        for token in tokens
        if token.casefold() not in FUNCTION_WORDS
    ]

    kept_lower = {token.casefold() for token in kept}
    for hint in hints:
        for word in hint.split():
            if word not in kept_lower:
                kept.append(word)
                kept_lower.add(word)

    cleaned = " ".join(kept).strip()
    if cleaned:
        return cleaned
    return " ".join(raw.split())


def _topic_terms(cleaned_query: str) -> Set[str]:
    """The meaningful terms of a query, for relevance checks.

    Function/question words are excluded. This matters now that the
    search query keeps its natural phrasing: if "many" were treated as a
    topic term, is_offtopic_wiki() would consider /wiki/Many on-topic and
    the dictionary-page guard would stop working.
    """
    return {
        token.casefold()
        for token in _QUERY_WORD.findall(cleaned_query)
        if token.casefold() not in FUNCTION_WORDS
    }


def score_result(url: str, topic_terms: Set[str]) -> int:
    """Heuristic relevance score for a result URL. Higher is better.

    Scraped result order often has little to do with how well a page
    answers the question: "who invented the transistor" returned YouTube
    support pages first, and "how many cats are in america" returned a
    chat-marketing vendor called manychat. Neither query phrasing avoids
    that on its own, so both phrasings are merged and ranked here rather
    than trusting provider order.

    Only the URL is used, because ranking happens before any fetch:
      +3  per topic term in the path (strongest signal)
      +2  per topic term in the hostname
      +2  path looks like an article (hyphenated multi-word slug),
          but only when the URL already matched a topic term -- an
          unrelated hyphenated slug is not evidence of relevance
      -4  host is rarely an answer (video/social/help-desk/shopping)
      -3  path looks like a search/listing/category page
      -4  host is a brand sign-in/account portal (matches the brand
          name but never answers a question about it)
      -2  no topic term matched anywhere in the URL
      +2  per extra distinct topic term matched (coverage bonus)
    """
    _matched, score = _score_detail(url, topic_terms)
    return score


def _score_detail(url: str, topic_terms: Set[str]) -> Tuple[int, int]:
    """Return (distinct topic terms matched, heuristic score)."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return (0, -100)

    host = (parts.hostname or "").casefold()
    path = (parts.path or "").casefold()
    path_words = set(_URL_WORD.findall(path))
    host_words = set(_URL_WORD.findall(host))

    def _matches(term: str, words: Set[str]) -> bool:
        stem = _stem(term)
        return any(term == w or stem == _stem(w) for w in words)

    score = 0
    matched_terms = 0
    for term in topic_terms:
        term = term.casefold()
        # Credit each term once, best placement wins. Summing host+path
        # let a brand double-dip (cats.com/cat-Breeds scored "cats"
        # twice) and outrank a page that actually answers the question.
        if _matches(term, path_words):
            score += 3
            matched_terms += 1
        elif _matches(term, host_words):
            score += 2
            matched_terms += 1

    # Multi-term coverage bonus. A page matching BOTH "invented" and
    # "transistor" is a better answer than one matching either alone, but
    # this stays a bonus rather than a primary sort key: as a primary key
    # it let a penalized sign-in page outrank a clean unrelated homepage.
    if matched_terms > 1:
        score += 2 * (matched_terms - 1)
    if matched_terms and any(
        "-" in seg for seg in path.split("/") if len(seg) > 8
    ):
        score += 2
    if any(host.startswith(prefix) for prefix in ACCOUNT_HOST_PREFIXES):
        score -= 4
    if topic_terms and not matched_terms:
        score -= 2
    if any(host == bad or host.endswith("." + bad) for bad in LOW_VALUE_HOSTS):
        score -= 4
    if any(marker in path for marker in LISTING_PATH_MARKERS):
        score -= 3
    return (matched_terms, score)


def rank_results(urls: Sequence[str], topic_terms: Set[str]) -> List[str]:
    """De-duplicate and sort URLs best-first, preserving order on ties.

    Sort key is (score, original position). Multi-term coverage is folded
    into the score as a bonus rather than used as a separate leading key,
    so a heavily penalized page can never ride one matched term above a
    cleaner result.
    """
    seen: Set[str] = set()
    unique: List[Tuple[int, int, str]] = []
    for position, url in enumerate(urls):
        key = normalize_url(url)
        if key in seen:
            continue
        seen.add(key)
        _matched, score = _score_detail(url, topic_terms)
        unique.append((-score, position, url))
    unique.sort()
    return [url for _, _, url in unique]


def _should_reject(url: str, topic_terms: Set[str]) -> bool:
    """Combined ingest-time relevance/junk check for a URL."""
    return is_junk_web_source(url, topic_terms)


def content_exists(
    index,
    content_hash: str,
) -> bool:
    """Return True if identical content already exists in the index."""
    try:
        row = index.conn.execute(
            """
            SELECT 1
            FROM sources
            WHERE content_hash = ?
            LIMIT 1
            """,
            (content_hash,),
        ).fetchone()
        return row is not None
    except Exception:
        return False


def crawl_urls_to_index(
    urls: Sequence[str],
    index,
    limit: int = 20,
    depth: int = 0,
    delay: float = DEFAULT_DELAY_SECONDS,
    same_domain_only: bool = True,
    topic_terms: Set[str] | None = None,
) -> int:
    """Crawl public URLs and add extracted text to the BrisartAI index."""
    try:
        crawl_limit = max(1, int(limit))
    except (TypeError, ValueError):
        crawl_limit = 20
    try:
        crawl_depth = max(0, int(depth))
    except (TypeError, ValueError):
        crawl_depth = 0
    try:
        crawl_delay = max(0.0, float(delay))
    except (TypeError, ValueError):
        crawl_delay = DEFAULT_DELAY_SECONDS

    topics = topic_terms or set()

    stats = CrawlStats()
    robots = RobotsCache()
    pending: "queue.Queue[Tuple[str, int, str]]" = queue.Queue()
    seen: Set[str] = set()

    for raw_url in urls:
        normalized = normalize_url(raw_url)
        if not normalized:
            continue
        if normalized in seen:
            continue
        if _should_reject(normalized, topics):
            print(f"SKIP off-topic/definition result: {normalized}")
            continue
        seen.add(normalized)
        pending.put((normalized, 0, normalized))

    crawled = 0
    while not pending.empty() and crawled < crawl_limit:
        current_url, level, root_url = pending.get()
        stats.requested += 1

        if _should_reject(current_url, topics):
            print(f"SKIP off-topic/definition result: {current_url}")
            continue

        if not robots.allowed(current_url):
            print(f"SKIP robots.txt: {current_url}")
            continue

        print(f"WEB FETCH depth={level}: {current_url}")
        result = fetch_url(current_url)

        if result.error:
            stats.errors += 1
            print(f"  WARN: {result.error}")
            continue

        if not result.text.strip():
            stats.skipped_empty += 1
            print("  WARN: page contained no extractable text")
            continue

        content_hash = stable_hash(result.text)
        if content_exists(index, content_hash):
            stats.skipped_duplicates += 1
            print("  SKIP duplicate content")
        else:
            indexed = index.add_source(
                source_type="web",
                location=result.url,
                title=result.title,
                text=result.text,
                content_hash=content_hash,
                size_bytes=len(
                    result.text.encode("utf-8", errors="replace")
                ),
                extension=".html",
            )
            if indexed:
                crawled += 1
                stats.indexed += 1
                print(
                    f"  OK: {len(result.text)} chars, "
                    f"{len(result.links)} links"
                )

        if level < crawl_depth:
            for link in result.links:
                normalized_link = normalize_url(link)
                if not normalized_link:
                    continue
                if _should_reject(normalized_link, topics):
                    continue
                if same_domain_only and not same_site(
                    root_url,
                    normalized_link,
                ):
                    continue
                if normalized_link in seen:
                    continue
                seen.add(normalized_link)
                pending.put((normalized_link, level + 1, root_url))

        if crawl_delay:
            time.sleep(crawl_delay)

    stats.print_summary()
    return crawled


def web_search_and_ingest(
    query: str,
    index,
    limit: int = 5,
    crawl_depth: int = 0,
) -> int:
    """Search the web and ingest the relevant, non-junk result pages.

    The question is searched twice -- once in its natural phrasing and
    once as bare keywords -- because neither form is reliably better.
    Results are merged, de-duplicated, filtered for dictionary hosts and
    off-topic disambiguation pages, then ranked by score_result() so the
    best `limit` pages are crawled regardless of provider ordering.
    """
    search_terms = clean_search_query(query)
    fallback_terms = search_keyword_fallback(query)

    if search_terms != query:
        print(f"Web search terms: {search_terms!r} (from: {query!r})")
    else:
        print(f"Web search terms: {search_terms!r}")

    # Both phrasings are searched and merged. An A/B over three queries
    # showed neither form wins on its own: the phrased question found the
    # right transistor pages where keywords returned YouTube help desks,
    # but keywords found real cat-population sources where the phrased
    # question returned Wikipedia trivia. Union + rank beats picking one.
    topics = _topic_terms(search_terms) | _topic_terms(fallback_terms)

    collected: List[str] = list(search_public_web(search_terms, limit=limit))

    if fallback_terms and fallback_terms != search_terms:
        print(f"Also searching keyword form: {fallback_terms!r}")
        collected.extend(search_public_web(fallback_terms, limit=limit))

    kept = [link for link in collected if not _should_reject(link, topics)]
    removed = len(collected) - len(kept)
    if removed:
        print(
            f"Filtered out {removed} off-topic/definition result(s) "
            "before crawling."
        )

    filtered = rank_results(kept, topics)[:limit]

    if not filtered:
        print(
            "No usable public search results were found or the provider "
            "was unavailable."
        )
        return 0

    print("Search results:")
    for number, link in enumerate(filtered, start=1):
        print(f"[{number}] {link}")

    return crawl_urls_to_index(
        filtered,
        index,
        limit=limit,
        depth=crawl_depth,
        same_domain_only=True,
        topic_terms=topics,
    )


__all__ = [
    "DEFAULT_DELAY_SECONDS",
    "clean_search_query",
    "content_exists",
    "crawl_urls_to_index",
    "search_keyword_fallback",
    "web_search_and_ingest",
]
