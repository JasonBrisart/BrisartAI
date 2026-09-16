"""
File: brisart_ai/web/crawler.py

Purpose
-------
The single chokepoint every web page must pass through to get indexed:
normalize the query, rank the resulting URLs, filter out known-junk
hosts and off-topic disambiguation pages, respect robots.txt, fetch and
de-duplicate content, apply a positive content-relevance gate, and add
the survivors to the index.

Communication / relationships
------------------------------
- brisart_ai/ui/service.py: web_search_and_ingest() is the entry point.
- Imports brisart_ai.blocklist.*, brisart_ai.intent.*,
  brisart_ai.knowledge.ranker.phrase_match_adjust,
  brisart_ai.util.{normalize_url, same_site, stable_hash},
  brisart_ai.web.fetcher.fetch_url, brisart_ai.web.search.search_public_web,
  brisart_ai.web.policy.RobotsCache, brisart_ai.web.stats.CrawlStats.
  Also imports brisart_ai.native.brisart_url.{brisart_unquote,
  brisart_urlsplit} (replacing urllib.parse.urlsplit/unquote) -- see
  brisart_ai/native/README.md for verification.

Settings / parameters
----------------------
- DEFAULT_DELAY_SECONDS (1.0).
- INTENT_WEIGHT (2) / PHRASE_MATCH_BONUS (4).
- _INTENT_HINTS.
- PAGE_RELEVANCE_SCAN_CHARS (5000): how much of a fetched page's body
  the crawl-time relevance gate scans for topic vocabulary (title is
  always scanned in full). Bounded so a very large page does not make
  the gate expensive.

Edge cases
----------
- _stem(): crude suffix stripper.
- Article-slug bonus checks both "-" and "_".
- content_exists() swallows any exception, returns False.
- score_result()/_score_detail()/rank_results()/explain_ranking() all
  accept an optional snippet (or snippets map), purely additive: omitting
  it is byte-identical to prior behavior. A term matched only in the
  snippet (not path/host/title) contributes a smaller score bump than a
  title match, per KI-006's resolution.
- crawl_urls_to_index() applies a POSITIVE content-relevance gate
  (_page_is_on_topic) after a page is fetched but before it is indexed:
  a page whose title+body shares NO topic vocabulary with the query --
  by whole word, single-'s' plural fold, OR shared stem -- is dropped
  and never enters the index (see Fix 1). The gate is deliberately
  permissive: it only drops a page that matches NONE of those tests, so
  it can never drop a page that shares real topic vocabulary with the
  query that found it. When topic_terms is empty (nothing to gate on)
  every page is kept, exactly as before.

Known limitations
-----------------
- The relevance gate is lexical (whole-word/plural/stem overlap), not
  semantic; a genuinely relevant page phrased with entirely different
  vocabulary than the query would be dropped, and a page that merely
  mentions a topic word in passing is kept. It is a junk-decoy filter,
  not a fine-grained ranker -- fine-grained ordering remains ranking's
  job at query time.
- Crawl politeness is a fixed DEFAULT_DELAY_SECONDS plus robots policy;
  there is no adaptive rate limiting per host.
- search_keyword_fallback() is a lexical fallback; it cannot recover
  results a provider never returned.

Fix 1 (2026-09-16): Off-topic pages could be permanently ingested into
the local index. crawl_urls_to_index() only rejected known-junk HOSTS
(is_junk_web_source / _should_reject) before indexing; it never checked
whether a fetched page's actual CONTENT was related to the query. When a
search provider was throttled and returned decoy pages (or an otherwise-
unrelated page slipped through host filtering), that page was fetched,
passed the host check, and was written into brisart_ai_index.sqlite3
permanently -- polluting every future query, since the index persists
across sessions (this was tracked as KI-002). Fixed by adding a positive
content-relevance gate, _page_is_on_topic(), applied after fetch and
before indexing: a page whose title+body shares no whole-word / plural /
stemmed topic term with the query is dropped (counted as
stats.skipped_offtopic) instead of indexed. The gate matches the
whole-word + single-'s' plural-fold approach web/search.py's
_partition_related_results() already uses, extended with the crawler's
own _stem(), and is permissive by construction so it can never drop a
page that shares real topic vocabulary with the query.

Examples
--------
    >>> clean_search_query("  who founded microsoft??  ")
    'who founded microsoft'
    >>> _page_is_on_topic("Book a Taxi", "Reserve your ride now.", {"cats"})
    False
    >>> _page_is_on_topic("Pet cat stats", "73.8 million cats.", {"cats"})
    True
    >>> # full ingest requires network + an index
    >>> web_search_and_ingest("who founded microsoft", index)   # doctest: +SKIP
"""

from __future__ import annotations

import queue
import re
import time
from typing import Dict, List, Optional, Sequence, Set, Tuple

from brisart_ai.blocklist import (
    ACCOUNT_HOST_PREFIXES, FUNCTION_WORDS, LISTING_PATH_MARKERS,
    LOW_VALUE_HOSTS, is_junk_web_source,
)
from brisart_ai.intent import INTENT_GENERAL, describe_intent, detect_intent, score_intent
from brisart_ai.knowledge.ranker import phrase_match_adjust
from brisart_ai.native.brisart_url import brisart_unquote, brisart_urlsplit
from brisart_ai.util import normalize_url, same_site, stable_hash
from brisart_ai.web.fetcher import fetch_url
from brisart_ai.web.search import search_public_web
from brisart_ai.web.policy import RobotsCache
from brisart_ai.web.stats import CrawlStats

DEFAULT_DELAY_SECONDS = 1.0

_INTENT_HINTS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("how", "many"), "number"), (("how", "much"), "amount"),
    (("how", "old"), "age"), (("how", "tall"), "height"),
    (("how", "long"), "length duration"), (("how", "far"), "distance"),
    (("population", "of"), "population"),
)

_QUERY_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-']*")
_URL_WORD = re.compile(r"[A-Za-z0-9]+")

_STEM_SUFFIXES = (
    "ations", "ation", "ings", "ing", "ors", "or", "ers", "er",
    "ions", "ion", "ed", "es", "s",
)


def _stem(word: str) -> str:
    word = word.casefold()
    for suffix in _STEM_SUFFIXES:
        floor = 3 if suffix in ("s", "es") else 4
        if len(word) - len(suffix) >= floor and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def clean_search_query(query: str) -> str:
    """Normalize a question for web search, keeping its natural phrasing."""
    raw = str(query or "")
    normalized = " ".join(raw.split())
    stripped = normalized.strip().strip("?!.,;:").strip()
    return stripped or normalized


def search_keyword_fallback(query: str) -> str:
    """Keyword-only form of a question, tried when the phrased query fails."""
    raw = str(query or "")
    lowered = " " + " ".join(raw.lower().split()) + " "
    hints: List[str] = []
    for phrase, hint in _INTENT_HINTS:
        needle = " " + " ".join(phrase) + " "
        if needle in lowered:
            hints.append(hint)
    tokens = _QUERY_WORD.findall(raw)
    kept = [token for token in tokens if token.casefold() not in FUNCTION_WORDS]
    kept_lower = {token.casefold() for token in kept}
    for hint in hints:
        for word in hint.split():
            if word not in kept_lower:
                kept.append(word)
                kept_lower.add(word)
    cleaned = " ".join(kept).strip()
    return cleaned if cleaned else " ".join(raw.split())


def _topic_terms(cleaned_query: str) -> Set[str]:
    return {
        token.casefold() for token in _QUERY_WORD.findall(cleaned_query)
        if token.casefold() not in FUNCTION_WORDS
    }


INTENT_WEIGHT = 2
PHRASE_MATCH_BONUS = 4
PAGE_RELEVANCE_SCAN_CHARS = 5000


def _page_is_on_topic(title: str, text: str, topic_terms: Set[str]) -> bool:
    """Positive content-relevance gate for a fetched page (see Fix 1).

    True when the page's title + (bounded) body shares at least one
    meaningful query term with `topic_terms` -- by exact whole word, by a
    symmetric single-'s' plural fold, or by shared stem. Deliberately
    PERMISSIVE: only a page matching NONE of those tests is judged
    off-topic, so a page sharing real topic vocabulary is never dropped.
    An empty `topic_terms` (nothing to gate on) always returns True, and
    a page with no extractable words returns False."""
    if not topic_terms:
        return True
    haystack = f"{title or ''} {str(text or '')[:PAGE_RELEVANCE_SCAN_CHARS]}"
    page_tokens = {word.casefold() for word in _URL_WORD.findall(haystack)}
    if not page_tokens:
        return False
    page_stems = {_stem(token) for token in page_tokens}
    for term in topic_terms:
        term = term.casefold()
        if term in page_tokens:
            return True
        if (term + "s") in page_tokens or (term.endswith("s") and term[:-1] in page_tokens):
            return True
        if _stem(term) in page_stems:
            return True
    return False


def score_result(url: str, topic_terms: Set[str], query: str = "", title: str = "", snippet: str = "") -> int:
    """Heuristic relevance score for a result URL. Higher is better."""
    _matched, score = _score_detail(url, topic_terms, query, title, snippet)
    return score


def _score_detail(url: str, topic_terms: Set[str], query: str = "", title: str = "", snippet: str = "") -> Tuple[int, int]:
    try:
        parts = brisart_urlsplit(url)
    except ValueError:
        return (0, -100)
    host = (parts.hostname or "").casefold()
    path = (parts.path or "").casefold()
    path_words = set(_URL_WORD.findall(path))
    host_words = set(_URL_WORD.findall(host))
    title_words = set(_URL_WORD.findall(str(title or "").casefold()))
    snippet_words = set(_URL_WORD.findall(str(snippet or "").casefold()))

    def _matches(term: str, words: Set[str]) -> bool:
        stem = _stem(term)
        return any(term == w or stem == _stem(w) for w in words)

    score = 0
    matched_terms = 0
    for term in topic_terms:
        term = term.casefold()
        if _matches(term, path_words):
            score += 3
            matched_terms += 1
        elif _matches(term, host_words) or _matches(term, title_words):
            score += 2
            matched_terms += 1
        elif _matches(term, snippet_words):
            # A snippet-only match is real signal (see KI-006) but weaker
            # than a title/host match -- the answer word appearing only in
            # the page's own description text, not its title, warrants a
            # smaller bump than a title match earns.
            score += 1
            matched_terms += 1
    if matched_terms > 1:
        score += 2 * (matched_terms - 1)
    if matched_terms and any(
        ("-" in seg or "_" in seg) for seg in path.split("/") if len(seg) > 8
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
    if query:
        phrase_haystack = f"{_intent_text(url)} {title or ''} {snippet or ''}"
        phrase_factor, _phrase_hits = phrase_match_adjust(query, phrase_haystack)
        if phrase_factor != 1.0:
            score += PHRASE_MATCH_BONUS
    if query:
        intent = detect_intent(query)
        if intent != INTENT_GENERAL:
            delta, _boosts, _penalties = score_intent(
                f"{_intent_text(url)} {title or ''} {snippet or ''}", intent, query, topic_terms=topic_terms,
            )
            score += int(round(delta * INTENT_WEIGHT))
    return (matched_terms, score)


def _intent_text(url: str) -> str:
    """Return a URL in a form the intent scorer can read (decoded, underscores as spaces)."""
    text = str(url or "")
    try:
        text = brisart_unquote(text)
    except (UnicodeDecodeError, ValueError):
        pass
    return text.replace("_", " ")


def rank_results(
    urls: Sequence[str], topic_terms: Set[str], query: str = "",
    titles: Optional[Dict[str, str]] = None,
    snippets: Optional[Dict[str, str]] = None,
) -> List[str]:
    """De-duplicate and sort URLs best-first, preserving order on ties."""
    seen: Set[str] = set()
    unique: List[Tuple[int, int, str]] = []
    for position, url in enumerate(urls):
        key = normalize_url(url)
        if key in seen:
            continue
        seen.add(key)
        title = (titles or {}).get(key, "")
        snippet = (snippets or {}).get(key, "")
        _matched, score = _score_detail(url, topic_terms, query, title, snippet)
        unique.append((-score, position, url))
    unique.sort()
    return [url for _, _, url in unique]


def explain_ranking(
    urls: Sequence[str], topic_terms: Set[str], query: str = "",
    titles: Optional[Dict[str, str]] = None,
    snippets: Optional[Dict[str, str]] = None,
) -> List[dict]:
    """Per-URL scoring breakdown, best-first -- used by the replay scripts."""
    intent = detect_intent(query) if query else INTENT_GENERAL
    rows: List[dict] = []
    seen: Set[str] = set()
    for position, url in enumerate(urls):
        key = normalize_url(url)
        if key in seen:
            continue
        seen.add(key)
        title = (titles or {}).get(key, "")
        snippet = (snippets or {}).get(key, "")
        matched, total = _score_detail(url, topic_terms, query, title, snippet)
        _base_matched, base = _score_detail(url, topic_terms, "", "")
        if intent != INTENT_GENERAL:
            delta, boosts, penalties = score_intent(
                f"{_intent_text(url)} {title or ''} {snippet or ''}", intent, query, topic_terms=topic_terms,
            )
        else:
            delta, boosts, penalties = (0.0, [], [])
        phrase_matched = False
        if query:
            phrase_factor, _hits = phrase_match_adjust(query, f"{_intent_text(url)} {title or ''} {snippet or ''}")
            phrase_matched = phrase_factor != 1.0
        rows.append({
            "url": url, "title": title, "position": position,
            "terms_matched": matched, "base_score": base,
            "phrase_matched": phrase_matched, "intent": intent,
            "intent_delta": int(round(delta * INTENT_WEIGHT)),
            "boosts": boosts, "penalties": penalties, "score": total,
        })
    rows.sort(key=lambda row: (-row["score"], row["position"]))
    return rows


def _should_reject(url: str, topic_terms: Set[str]) -> bool:
    """Combined ingest-time relevance/junk check for a URL."""
    return is_junk_web_source(url, topic_terms)


def content_exists(index, content_hash: str) -> bool:
    """Return True if identical content already exists in the index."""
    try:
        row = index.conn.execute(
            "SELECT 1 FROM sources WHERE content_hash = ? LIMIT 1", (content_hash,),
        ).fetchone()
        return row is not None
    except Exception:
        return False


def crawl_urls_to_index(
    urls: Sequence[str], index, limit: int = 20, depth: int = 0,
    delay: float = DEFAULT_DELAY_SECONDS, same_domain_only: bool = True,
    topic_terms: Set[str] | None = None,
) -> int:
    """Crawl public URLs and add extracted text to the BrisartAI index.

    Every fetched page must pass a positive content-relevance gate
    (_page_is_on_topic) before it is indexed: a page whose title+body
    shares no topic vocabulary with the query is dropped rather than
    permanently ingested (see Fix 1). The gate is skipped only when
    topic_terms is empty (nothing to gate on)."""
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
        if not normalized or normalized in seen:
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
        # Positive content-relevance gate (Fix 1): refuse to index a page
        # whose content shares no topic vocabulary with the query, so a
        # throttled/decoy or otherwise-unrelated page can never enter the
        # index and pollute future queries. Permissive by construction --
        # a page sharing any real topic term is kept.
        if not _page_is_on_topic(result.title, result.text, topics):
            stats.skipped_offtopic += 1
            print("  SKIP off-topic page content (shares no topic vocabulary with the query)")
            continue
        content_hash = stable_hash(result.text)
        if content_exists(index, content_hash):
            stats.skipped_duplicates += 1
            print("  SKIP duplicate content")
        else:
            indexed = index.add_source(
                source_type="web", location=result.url, title=result.title,
                text=result.text, content_hash=content_hash,
                size_bytes=len(result.text.encode("utf-8", errors="replace")),
                extension=".html",
            )
            if indexed:
                crawled += 1
                stats.indexed += 1
                print(f"  OK: {len(result.text)} chars, {len(result.links)} links")
        if level < crawl_depth:
            for link in result.links:
                normalized_link = normalize_url(link)
                if not normalized_link:
                    continue
                if _should_reject(normalized_link, topics):
                    continue
                if same_domain_only and not same_site(root_url, normalized_link):
                    continue
                if normalized_link in seen:
                    continue
                seen.add(normalized_link)
                pending.put((normalized_link, level + 1, root_url))
        if crawl_delay:
            time.sleep(crawl_delay)

    stats.print_summary()
    return crawled


def web_search_and_ingest(query: str, index, limit: int = 5, crawl_depth: int = 0) -> int:
    """Search the web and ingest the relevant, non-junk result pages."""
    search_terms = clean_search_query(query)
    fallback_terms = search_keyword_fallback(query)
    intent = detect_intent(query)
    print(f"Detected intent: {describe_intent(intent, query)}")
    if search_terms != query:
        print(f"Web search terms: {search_terms!r} (from: {query!r})")
    else:
        print(f"Web search terms: {search_terms!r}")

    topics = _topic_terms(search_terms) | _topic_terms(fallback_terms)

    collected: List[Tuple[str, str, str]] = list(
        search_public_web(search_terms, limit=limit, with_snippets=True)
    )
    if fallback_terms and fallback_terms != search_terms:
        print(f"Also searching keyword form: {fallback_terms!r}")
        collected.extend(search_public_web(fallback_terms, limit=limit, with_snippets=True))

    kept_pairs = [(url, title, snippet) for url, title, snippet in collected if not _should_reject(url, topics)]
    removed = len(collected) - len(kept_pairs)
    if removed:
        print(f"Filtered out {removed} off-topic/definition result(s) before crawling.")

    titles_map: Dict[str, str] = {}
    snippets_map: Dict[str, str] = {}
    for url, title, snippet in kept_pairs:
        key = normalize_url(url)
        if key and title and key not in titles_map:
            titles_map[key] = title
        if key and snippet and key not in snippets_map:
            snippets_map[key] = snippet

    kept = [url for url, _title, _snippet in kept_pairs]
    filtered = rank_results(kept, topics, query, titles=titles_map, snippets=snippets_map)[:limit]
    if not filtered:
        print("No usable public search results were found or the provider was unavailable.")
        return 0

    print("Search results:")
    for number, link in enumerate(filtered, start=1):
        title = titles_map.get(normalize_url(link), "")
        if title:
            print(f"[{number}] {link}  (title: {title!r})")
        else:
            print(f"[{number}] {link}")

    return crawl_urls_to_index(
        filtered, index, limit=limit, depth=crawl_depth,
        same_domain_only=True, topic_terms=topics,
    )


__all__ = [
    "DEFAULT_DELAY_SECONDS", "INTENT_WEIGHT", "PHRASE_MATCH_BONUS",
    "clean_search_query", "content_exists", "crawl_urls_to_index",
    "explain_ranking", "rank_results", "score_result",
    "search_keyword_fallback", "web_search_and_ingest",
]
