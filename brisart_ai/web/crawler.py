"""Public web crawling and ingestion for BrisartAI.

This module is the single chokepoint through which every web page must
pass to be indexed.

Three layers keep junk out of your answers:

1. QUERY CLEANING + INTENT HINTS: before a question is sent to a search
   engine, filler/question words are stripped, and the *intent* of the
   question is turned into a helpful keyword. "how many cats are in
   america" becomes the search "cats america number" -- the "many" is
   removed (so no dictionary card) and "number" is added (so results
   lean toward quantities/populations instead of random cat facts).
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
from typing import List, Sequence, Set, Tuple

from brisart_ai.blocklist import FUNCTION_WORDS, is_junk_web_source
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


def clean_search_query(query: str) -> str:
    """Strip filler words and append intent keywords for web search.

    "how many cats are in america" -> "cats america number"

    If every word is filler, the original whitespace-normalized query is
    returned so we never search for an empty string.
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
    """The meaningful terms of a cleaned query, for relevance checks."""
    return {
        token.casefold()
        for token in _QUERY_WORD.findall(cleaned_query)
    }


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

    The query is cleaned and given an intent keyword first, then results
    are filtered for dictionary hosts and off-topic disambiguation pages
    before crawling.
    """
    search_terms = clean_search_query(query)
    if search_terms != query:
        print(f"Web search terms: {search_terms!r} (from: {query!r})")
    else:
        print(f"Web search terms: {search_terms!r}")

    topics = _topic_terms(search_terms)

    links = search_public_web(search_terms, limit=limit)

    filtered: List[str] = [
        link for link in links if not _should_reject(link, topics)
    ]
    removed = len(links) - len(filtered)
    if removed:
        print(
            f"Filtered out {removed} off-topic/definition result(s) "
            "before crawling."
        )

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
    "web_search_and_ingest",
]
