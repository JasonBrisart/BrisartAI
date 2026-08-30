"""brisart_ai/web/crawler.py

The single chokepoint every web page must pass through to get indexed:
normalize the query, rank the resulting URLs, filter out known-junk
hosts and off-topic disambiguation pages, respect robots.txt, fetch and
de-duplicate content, and add the survivors to the index.

**Query phrasing.** A question keeps its natural phrasing when sent to
search (`clean_search_query()`), because that phrasing is what matches
pages actually containing the answer -- stripping "how many cats are in
america" down to bare keywords throws that signal away and returns
pages merely *about* cats. A keyword-only form
(`search_keyword_fallback()`) is kept as a secondary attempt for when
the phrased query returns nothing usable. `web_search_and_ingest()`
searches BOTH forms and merges results, because neither reliably wins
alone -- a live A/B test showed the phrased form found the right
technical pages where keywords returned help-desk pages, while keywords
found real statistical sources where the phrased form returned
encyclopedia trivia.

**Four layers of junk filtering**, in order: an off-topic Wikipedia page
whose title is itself a bare function word (`brisart_ai.blocklist`);
known dictionary/thesaurus hosts, refused at ingest time as a final
safety net; and title-and-phrase-aware ranking (below), so even survivors
are ordered by genuine relevance rather than provider order.

**Scoring a result URL** (`score_result()`/`_score_detail()`) is a small,
hand-tuned integer heuristic, not a learned model:
  +3  per topic term in the path (strongest signal)
  +2  per topic term in the hostname OR the result's own displayed title
      (each term credited once, at its best-scoring placement -- summing
      host+path let a brand name double-dip and outrank a real answer)
  +2  path looks like an article slug, only when a topic term already
      matched (an unrelated hyphenated slug isn't evidence on its own)
  +4  the literal query phrase appears in the URL+title text (detection
      delegated to knowledge/ranker.py's `phrase_match_adjust()`, so web
      and offline ranking can't silently disagree about what counts)
  -4  host is rarely an answer (video/social/help-desk/shopping)
  -3  path looks like a search/listing/category page
  -4  host is a brand's own sign-in/account portal
  -2  no topic term matched anywhere
  +2  per extra distinct topic term matched (coverage bonus)
An intent adjustment from `brisart_ai.intent` is folded in on top when a
query is supplied, at a weight (`INTENT_WEIGHT = 2`) tuned so genre
signal can reorder comparably-overlapping results but can't by itself
lift a page matching nothing.

One URL-decoding wrinkle worth knowing about: `_intent_text()`
percent-decodes a URL and converts underscores to spaces before intent
scoring, specifically because a live replay once ranked
`/wiki/Invented_%28album%29` at the top for "who invented the
transistor" -- the `(album)` qualifier that should have demoted it was
spelled `%28album%29`, so the work-of-art penalty never matched.

`crawl_urls_to_index()` treats the combined blocklist/off-topic check as
a filter applied both before a URL is first queued AND again when
dequeued, since a URL discovered as an outbound link mid-crawl hasn't
been checked yet at the time it was queued.
"""
from __future__ import annotations

import queue
import re
import time
import urllib.parse
from typing import Dict, List, Optional, Sequence, Set, Tuple

from brisart_ai.blocklist import (
    ACCOUNT_HOST_PREFIXES,
    FUNCTION_WORDS,
    LISTING_PATH_MARKERS,
    LOW_VALUE_HOSTS,
    is_junk_web_source,
)
from brisart_ai.intent import (
    INTENT_GENERAL,
    describe_intent,
    detect_intent,
    score_intent,
)
from brisart_ai.knowledge.ranker import phrase_match_adjust
from brisart_ai.util import normalize_url, same_site, stable_hash
from brisart_ai.web.fetcher import fetch_url
from brisart_ai.web.search import search_public_web
from brisart_ai.web.policy import RobotsCache
from brisart_ai.web.stats import CrawlStats

DEFAULT_DELAY_SECONDS = 1.0

# Question-intent phrases mapped to a helpful search keyword, appended
# by search_keyword_fallback() so results lean toward the right KIND of
# answer. Longer phrases listed first so the most specific intent wins.
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

# URL tokenizer -- deliberately different from _QUERY_WORD: inside a URL
# "-"/"_"/"." separate words, so "history-of-microsoft-1975" must
# tokenize to {history, of, microsoft, 1975}. Reusing _QUERY_WORD here
# was a real bug: it kept the slug as ONE token, so "microsoft" never
# matched and genuine articles scored as unrelated. Reused for a
# result's title text too, since a title is ordinary prose needing the
# same word-splitting a URL slug does.
_URL_WORD = re.compile(r"[A-Za-z0-9]+")

_STEM_SUFFIXES = (
    "ations", "ation", "ings", "ing", "ors", "or", "ers", "er",
    "ions", "ion", "ed", "es", "s",
)


def _stem(word: str) -> str:
    """Crude suffix stripper so query and URL word forms can meet.

    "who invented the transistor" should match a page about its
    "Invention" -- plain "s"-stripping missed that. Floored at 4
    characters (3 for plain s/es) so short words aren't mangled.
    """
    word = word.casefold()
    for suffix in _STEM_SUFFIXES:
        floor = 3 if suffix in ("s", "es") else 4
        if len(word) - len(suffix) >= floor and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def clean_search_query(query: str) -> str:
    """Normalize a question for web search, keeping its natural phrasing.

    Whitespace is normalized and trailing punctuation dropped; the
    question is otherwise passed through essentially intact, since
    natural phrasing is what search engines rank well against pages that
    actually answer it. Dictionary-hijacking is handled downstream by
    the shared blocklist, not by stripping words here.
    """
    raw = str(query or "")
    normalized = " ".join(raw.split())
    stripped = normalized.strip().strip("?!.,;:").strip()
    return stripped or normalized


def search_keyword_fallback(query: str) -> str:
    """Keyword-only form of a question, tried when the phrased query fails.

    Question words are removed and an intent keyword appended, e.g.
    "how many cats are in america" -> "cats america number". Finds
    topical pages but not necessarily answering ones -- that's why it's
    a fallback, not the primary form.
    """
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
    """Meaningful terms of a query, for relevance checks (function words excluded)."""
    return {
        token.casefold()
        for token in _QUERY_WORD.findall(cleaned_query)
        if token.casefold() not in FUNCTION_WORDS
    }


INTENT_WEIGHT = 2
PHRASE_MATCH_BONUS = 4


def score_result(url: str, topic_terms: Set[str], query: str = "", title: str = "") -> int:
    """Heuristic relevance score for a result URL. Higher is better.

    See the module docstring for the full scoring breakdown. `title` is
    optional (default "" reproduces pre-title-awareness URL-only
    behavior exactly) -- when supplied, typically from
    `search_public_web(with_titles=True)`, a result gets credit for
    topic terms living only in its displayed title.
    """
    _matched, score = _score_detail(url, topic_terms, query, title)
    return score


def _score_detail(url: str, topic_terms: Set[str], query: str = "", title: str = "") -> Tuple[int, int]:
    """Return (distinct topic terms matched, heuristic score)."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return (0, -100)

    host = (parts.hostname or "").casefold()
    path = (parts.path or "").casefold()
    path_words = set(_URL_WORD.findall(path))
    host_words = set(_URL_WORD.findall(host))
    title_words = set(_URL_WORD.findall(str(title or "").casefold()))

    def _matches(term: str, words: Set[str]) -> bool:
        stem = _stem(term)
        return any(term == w or stem == _stem(w) for w in words)

    score = 0
    matched_terms = 0
    for term in topic_terms:
        term = term.casefold()
        # Credit each term once, best placement wins.
        if _matches(term, path_words):
            score += 3
            matched_terms += 1
        elif _matches(term, host_words) or _matches(term, title_words):
            score += 2
            matched_terms += 1

    if matched_terms > 1:
        score += 2 * (matched_terms - 1)

    # Article-shaped slug. Both "-" and "_" count (Wikipedia uses "_",
    # most CMS platforms use "-") -- checking only "-" silently denied
    # this bonus to every encyclopedia article.
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
        phrase_haystack = f"{_intent_text(url)} {title or ''}"
        phrase_factor, _phrase_hits = phrase_match_adjust(query, phrase_haystack)
        if phrase_factor != 1.0:
            score += PHRASE_MATCH_BONUS

    if query:
        intent = detect_intent(query)
        if intent != INTENT_GENERAL:
            delta, _boosts, _penalties = score_intent(
                f"{_intent_text(url)} {title or ''}", intent, query, topic_terms=topic_terms,
            )
            score += int(round(delta * INTENT_WEIGHT))

    return (matched_terms, score)


def _intent_text(url: str) -> str:
    """Return a URL in a form the intent scorer can read (decoded, underscores as spaces).

    Percent-encoding hides genre markers -- a live replay ranked
    /wiki/Invented_%28album%29 at the top for "who invented the
    transistor" because the encoded (album) qualifier never matched the
    work-of-art penalty.
    """
    text = str(url or "")
    try:
        text = urllib.parse.unquote(text)
    except (UnicodeDecodeError, ValueError):
        pass
    return text.replace("_", " ")


def rank_results(
    urls: Sequence[str],
    topic_terms: Set[str],
    query: str = "",
    titles: Optional[Dict[str, str]] = None,
) -> List[str]:
    """De-duplicate and sort URLs best-first, preserving order on ties.

    `titles`, when supplied, maps normalized URL -> displayed result
    title (from `search_public_web(with_titles=True)`); folded into each
    URL's score alongside the URL itself.
    """
    seen: Set[str] = set()
    unique: List[Tuple[int, int, str]] = []
    for position, url in enumerate(urls):
        key = normalize_url(url)
        if key in seen:
            continue
        seen.add(key)
        title = (titles or {}).get(key, "")
        _matched, score = _score_detail(url, topic_terms, query, title)
        unique.append((-score, position, url))
    unique.sort()
    return [url for _, _, url in unique]


def explain_ranking(
    urls: Sequence[str],
    topic_terms: Set[str],
    query: str = "",
    titles: Optional[Dict[str, str]] = None,
) -> List[dict]:
    """Per-URL scoring breakdown, best-first -- used by the replay scripts.

    Ranking that can't be inspected can't be trusted, so every component
    of the final score is reported, including which title (if any) fed
    into it.
    """
    intent = detect_intent(query) if query else INTENT_GENERAL
    rows: List[dict] = []
    seen: Set[str] = set()
    for position, url in enumerate(urls):
        key = normalize_url(url)
        if key in seen:
            continue
        seen.add(key)

        title = (titles or {}).get(key, "")
        matched, total = _score_detail(url, topic_terms, query, title)
        _base_matched, base = _score_detail(url, topic_terms, "", "")

        if intent != INTENT_GENERAL:
            delta, boosts, penalties = score_intent(
                f"{_intent_text(url)} {title or ''}", intent, query, topic_terms=topic_terms,
            )
        else:
            delta, boosts, penalties = (0.0, [], [])

        phrase_matched = False
        if query:
            phrase_factor, _hits = phrase_match_adjust(query, f"{_intent_text(url)} {title or ''}")
            phrase_matched = phrase_factor != 1.0

        rows.append(
            {
                "url": url, "title": title, "position": position,
                "terms_matched": matched, "base_score": base,
                "phrase_matched": phrase_matched, "intent": intent,
                "intent_delta": int(round(delta * INTENT_WEIGHT)),
                "boosts": boosts, "penalties": penalties, "score": total,
            }
        )
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
    """Search the web and ingest the relevant, non-junk result pages.

    The question is searched twice -- natural phrasing and bare keywords
    -- with titles preserved, merged, filtered, then ranked by
    `rank_results()` (title- and phrase-aware, not just URL-aware) before
    the best `limit` pages are actually crawled.
    """
    search_terms = clean_search_query(query)
    fallback_terms = search_keyword_fallback(query)

    intent = detect_intent(query)
    print(f"Detected intent: {describe_intent(intent, query)}")

    if search_terms != query:
        print(f"Web search terms: {search_terms!r} (from: {query!r})")
    else:
        print(f"Web search terms: {search_terms!r}")

    topics = _topic_terms(search_terms) | _topic_terms(fallback_terms)

    collected: List[Tuple[str, str]] = list(
        search_public_web(search_terms, limit=limit, with_titles=True)
    )
    if fallback_terms and fallback_terms != search_terms:
        print(f"Also searching keyword form: {fallback_terms!r}")
        collected.extend(search_public_web(fallback_terms, limit=limit, with_titles=True))

    kept_pairs = [(url, title) for url, title in collected if not _should_reject(url, topics)]
    removed = len(collected) - len(kept_pairs)
    if removed:
        print(f"Filtered out {removed} off-topic/definition result(s) before crawling.")

    titles_map: Dict[str, str] = {}
    for url, title in kept_pairs:
        key = normalize_url(url)
        if key and title and key not in titles_map:
            titles_map[key] = title

    kept = [url for url, _title in kept_pairs]
    filtered = rank_results(kept, topics, query, titles=titles_map)[:limit]

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
