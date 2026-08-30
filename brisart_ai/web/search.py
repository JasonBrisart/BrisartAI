"""brisart_ai/web/search.py

Dependency-free public web search across seven providers, tried in
order from MOST likely to be blocked to LEAST likely: Startpage -> Brave
Search -> DuckDuckGo HTML -> DuckDuckGo Lite -> Bing HTML -> Mojeek ->
Wikipedia API. Every provider before the Wikipedia API is an HTML
scraper, fragile in a different way (heavy bot-detection, explicit
challenge pages, rate-limiting, undocumented markup) -- rather than
trying the most-established providers first, the chain spends its
riskiest request first, so each subsequent provider is both a fallback
for the ones before it and a strictly safer bet in its own right. The
Wikipedia API runs last as a stable, key-free floor on quality that
keeps working under exactly the conditions that break every scraper
above it, at the cost of covering only encyclopedic topics.

Only organic result links are extracted from each provider's HTML;
results are normalized (tracking params stripped, redirect wrappers
unwound), deduplicated, and relatedness-filtered per result before
being handed back to the crawler.

**Two different extraction strategies, because two different levels of
markup knowledge exist.** For DuckDuckGo and Bing, `_ResultLinkParser`
recognizes known result-link CSS classes or anchors nested in `<h2>`/
`<h3>` result-title headings. For Mojeek/Brave/Startpage, whose markup
is either undocumented or changes often (Brave's own scraping notes
call their result markup "unlabeled" and something that "shifts
often"), `_extract_result_links()` instead uses domain-based heuristics
-- a link's host must simply differ from the search engine's own host
and not be one of its help/account/static subdomains. This is less
precise on day one than a hand-tuned selector, but degrades gracefully
("still gets titles and URLs, maybe a rougher snippet") instead of
silently returning nothing the next time markup changes.

**IMPORTANT -- unverified against a live fetch.** The exact current HTML
structure of Mojeek, Brave Search, and Startpage was not verified
against a live fetch during development. If one of these providers
returns zero results for a query known to have results, it's most
likely serving a challenge/consent page, or its markup has changed
enough that even the generic extractor can no longer find outbound
links.

**Per-result relatedness, not per-batch.** `_partition_related_results()`
judges each `(url, title)` pair individually against the query's
meaningful terms, rather than the older whole-batch check (which only
asked "does *any* result in this batch share a query term?" -- a single
good result waved an entire batch through, garbage included). A single
genuinely unrelated result riding alongside good ones is dropped on its
own now. If partitioning would drop EVERY result in a batch, that's
still treated as a throttled/decoy response and the whole batch is
discarded, preserving the old whole-batch safety valve as a special
case.

`_decode_bing_target()` unwraps Bing's `/ck/a` click-tracking redirect
(base64url-decoding the `u` parameter after its short encoding-tag
prefix); if unwrapping fails for any reason, the original wrapped URL is
returned unchanged rather than raising. `_normalize_result_url()`
rejects a candidate outright if its host is one of the search engine's
own hosts or a blocked dictionary host, independent of the later
relatedness partitioning.
"""
from __future__ import annotations

import base64
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Optional, Sequence, Tuple, Union

from brisart_ai.blocklist import FUNCTION_WORDS, is_blocked_web_host
from brisart_ai.util import normalize_url
from brisart_ai.web.fetcher import MAX_PAGE_BYTES, REQUEST_TIMEOUT
from brisart_ai.web.policy import USER_AGENT

DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"
DUCKDUCKGO_LITE_URL = "https://lite.duckduckgo.com/lite/"
BING_SEARCH_URL = "https://www.bing.com/search"
MOJEEK_SEARCH_URL = "https://www.mojeek.com/search"
BRAVE_SEARCH_URL = "https://search.brave.com/search"
STARTPAGE_SEARCH_URL = "https://www.startpage.com/sp/search"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_ARTICLE_BASE = "https://en.wikipedia.org/wiki/"

_BLOCK_MARKERS = (
    "anomaly-modal", "anomaly.js", "bots use duckduckgo", "captcha",
    "challenge-form", "detected unusual traffic", "human verification",
    "operation timed out", "rate limit", "ratelimit", "too many requests",
)

_SEARCH_HOSTS = {
    "duckduckgo.com", "html.duckduckgo.com", "lite.duckduckgo.com",
    "www.duckduckgo.com", "bing.com", "www.bing.com", "cc.bingj.com",
    "go.microsoft.com", "login.live.com", "account.microsoft.com",
    "support.microsoft.com", "r.bing.com", "mojeek.com", "www.mojeek.com",
    "search.brave.com", "www.startpage.com", "startpage.com",
}

_IGNORED_SCHEMES = ("javascript:", "mailto:", "tel:", "data:")

# CSS classes marking an anchor as an *organic* result link rather than
# chrome, ads, or dictionary/knowledge-panel widgets.
_RESULT_LINK_CLASSES = (
    "result__a",     # DuckDuckGo HTML organic result title
    "result-link",   # DuckDuckGo Lite organic result title
    "result__url",   # DuckDuckGo HTML visible URL anchor
)

# Header tags wrapping organic result titles where the anchor itself
# carries no distinctive class (notably Bing).
_RESULT_TITLE_TAGS = ("h2", "h3")


class _ResultLinkParser(HTMLParser):
    """Collect only *organic search result* anchor URLs.

    An anchor counts as an organic result when its class matches a known
    result-link class (DuckDuckGo), or it's nested inside an <h2>/<h3>
    result-title heading (Bing and DuckDuckGo fallbacks). Everything
    else -- nav, ads, sidebars, "people also ask," footer links -- is
    ignored.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: List[Tuple[str, str]] = []
        self._title_depth = 0
        self._capturing = False
        self._current_href = ""
        self._current_text: List[str] = []

    def _class_is_result(self, attrs) -> bool:
        for name, value in attrs:
            if name.casefold() != "class" or not value:
                continue
            classes = {token.casefold() for token in value.split()}
            for result_class in _RESULT_LINK_CLASSES:
                if result_class in classes:
                    return True
        return False

    def handle_starttag(self, tag, attrs) -> None:
        lowered_tag = tag.casefold()
        if lowered_tag in _RESULT_TITLE_TAGS:
            self._title_depth += 1
            return
        if lowered_tag != "a":
            return

        href = ""
        for name, value in attrs:
            if name.casefold() == "href" and value:
                href = html.unescape(value)
                break
        if not href:
            return

        if self._title_depth > 0 or self._class_is_result(attrs):
            self._capturing = True
            self._current_href = href
            self._current_text = []

    def handle_data(self, data) -> None:
        if self._capturing:
            self._current_text.append(str(data))

    def handle_endtag(self, tag) -> None:
        lowered_tag = tag.casefold()
        if lowered_tag in _RESULT_TITLE_TAGS:
            if self._title_depth > 0:
                self._title_depth -= 1
            return
        if lowered_tag != "a":
            return
        if self._capturing and self._current_href:
            text = " ".join(part.strip() for part in self._current_text if part.strip())
            self.links.append((self._current_href, text))
        self._capturing = False
        self._current_href = ""
        self._current_text = []


def _request_headers() -> Dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,text/xml;q=0.9,"
            "text/plain;q=0.8,*/*;q=0.5"
        ),
        "Accept-Language": "en-US,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "close",
    }


def _read_response(response) -> str:
    raw = response.read(MAX_PAGE_BYTES + 1)
    if len(raw) > MAX_PAGE_BYTES:
        raise ValueError("search response exceeded maximum size")
    charset = response.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def _http_get(url: str, parameters: Optional[Dict[str, str]] = None) -> Optional[str]:
    request_url = url
    if parameters:
        encoded = urllib.parse.urlencode(parameters)
        separator = "&" if "?" in request_url else "?"
        request_url = f"{request_url}{separator}{encoded}"

    request = urllib.request.Request(request_url, headers=_request_headers(), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return _read_response(response)
    except urllib.error.HTTPError as exc:
        print(f"WARN: search provider returned HTTP {exc.code}: {request_url}")
    except urllib.error.URLError as exc:
        print(f"WARN: search provider network error: {exc.reason}")
    except Exception as exc:
        print(f"WARN: search provider request failed: {exc}")
    return None


def _http_post(url: str, parameters: Dict[str, str]) -> Optional[str]:
    encoded = urllib.parse.urlencode(parameters).encode("utf-8")
    headers = _request_headers()
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    headers["Origin"] = "https://duckduckgo.com"
    headers["Referer"] = "https://duckduckgo.com/"
    request = urllib.request.Request(url, data=encoded, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return _read_response(response)
    except urllib.error.HTTPError as exc:
        print(f"WARN: search provider returned HTTP {exc.code}: {url}")
    except urllib.error.URLError as exc:
        print(f"WARN: search provider network error: {exc.reason}")
    except Exception as exc:
        print(f"WARN: search provider request failed: {exc}")
    return None


def _looks_blocked(raw_text: str) -> bool:
    lowered = str(raw_text or "").casefold()
    return any(marker in lowered for marker in _BLOCK_MARKERS)


def _partition_related_results(
    query: str, results: Sequence[Tuple[str, str]],
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Split provider results into (related, unrelated), judged per-result.

    Each pair is judged individually against the query's meaningful
    terms (4+ letter words that aren't common function words) -- a
    deliberately low bar meant only to catch a wholesale topic mismatch,
    not to rank on-topic results against each other (that's
    knowledge/ranker.py's job once a page is indexed). Replaces an older
    whole-batch check that let a single good result wave through an
    entire batch, garbage included -- observed live, an unrelated
    "vandalism incident" Wikipedia page rode alongside two genuinely
    relevant pages and got indexed too.

    If `query` has no meaningful terms, every result is treated as
    related. If partitioning would drop EVERY result, that's still
    evidence of a throttled/decoy response -- callers should discard the
    whole batch, same as the old whole-batch check did.
    """
    terms = {
        word for word in re.findall(r"[a-z0-9]+", str(query or "").casefold())
        if len(word) > 3 and word not in FUNCTION_WORDS
    }
    if not terms:
        return list(results), []

    related: List[Tuple[str, str]] = []
    unrelated: List[Tuple[str, str]] = []
    for url, title in results:
        haystack = f"{url} {title}".casefold()
        matched = False
        for term in terms:
            stem = term.rstrip("s")
            if term in haystack or (len(stem) >= 3 and stem in haystack):
                matched = True
                break
        (related if matched else unrelated).append((url, title))
    return related, unrelated


def _is_search_host(hostname: str) -> bool:
    host = str(hostname or "").casefold().strip(".")
    if host in _SEARCH_HOSTS:
        return True
    return any(host.endswith("." + search_host) for search_host in _SEARCH_HOSTS)


def _remove_tracking_parameters(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return ""

    ignored_parameters = {
        "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src", "source",
        "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term",
    }
    parameters = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    cleaned_parameters = [
        (name, value) for name, value in parameters
        if name.casefold() not in ignored_parameters
    ]
    cleaned_query = urllib.parse.urlencode(cleaned_parameters, doseq=True)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, cleaned_query, ""))


def _decode_duckduckgo_target(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return ""
    if "duckduckgo.com" not in parsed.netloc.casefold():
        return url

    parameters = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    values = parameters.get("uddg")
    if not values:
        return url

    target = values[0]
    for _ in range(3):
        decoded = urllib.parse.unquote(target)
        if decoded == target:
            break
        target = decoded
    return target if target.startswith(("http://", "https://")) else url


def _decode_bing_target(url: str) -> str:
    """Unwrap Bing's /ck/a click-tracking redirect wrapper.

    Bing wraps organic result links as
    https://www.bing.com/ck/a?...&u=a1<base64url>&..., where the `u`
    parameter's value is prefixed with a short encoding tag ("a1")
    followed by URL-safe base64 without padding. Returns the original
    URL unchanged if unwrapping fails for any reason.
    """
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    if "bing.com" not in parsed.netloc.casefold():
        return url
    if not parsed.path.casefold().endswith("/ck/a"):
        return url

    parameters = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    values = parameters.get("u")
    if not values:
        return url

    encoded = values[0]
    if not encoded[2:]:
        return url
    payload = encoded[2:] if len(encoded) > 2 else encoded
    padding = "=" * (-len(payload) % 4)
    try:
        decoded_bytes = base64.urlsafe_b64decode(payload + padding)
        decoded = decoded_bytes.decode("utf-8", errors="replace")
    except Exception:
        return url
    return decoded if decoded.startswith(("http://", "https://")) else url


def _strip_embedded_markup(text: str) -> str:
    """Best-effort extraction of an href value from stray HTML.

    Search result text should already be a bare URL. If a provider ever
    hands back a whole anchor tag as the value instead, pull the real
    destination out of the href="..." attribute rather than treating the
    markup blob as the URL itself.
    """
    candidate = str(text or "").strip()
    if "<" not in candidate or "href" not in candidate.casefold():
        return candidate
    marker = "href="
    lowered = candidate.casefold()
    start = lowered.find(marker)
    if start == -1:
        return candidate
    start += len(marker)
    if start >= len(candidate):
        return candidate
    quote_char = candidate[start]
    if quote_char not in ("'", '"'):
        return candidate
    end = candidate.find(quote_char, start + 1)
    if end == -1:
        return candidate
    return candidate[start + 1:end]


def _normalize_result_url(href: str, base_url: str) -> str:
    candidate = html.unescape(_strip_embedded_markup(href))
    if not candidate:
        return ""
    lowered = candidate.casefold()
    if lowered.startswith(_IGNORED_SCHEMES):
        return ""

    if candidate.startswith("//"):
        candidate = "https:" + candidate
    else:
        candidate = urllib.parse.urljoin(base_url, candidate)

    candidate = _decode_duckduckgo_target(candidate)
    candidate = _decode_bing_target(candidate)
    candidate = _remove_tracking_parameters(candidate)
    candidate = normalize_url(candidate)
    if not candidate:
        return ""

    try:
        parsed = urllib.parse.urlsplit(candidate)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"}:
        return ""
    if not parsed.hostname:
        return ""
    if _is_search_host(parsed.hostname):
        return ""
    if is_blocked_web_host(candidate):
        return ""
    return candidate


def _deduplicate(results: Sequence[Tuple[str, str]], limit: int) -> List[Tuple[str, str]]:
    """Deduplicate (url, title) pairs, preserving order.

    Titles ride along so provider-level relevance checks can inspect
    displayed result text, and so with_titles=True callers get real
    titles for title-aware ranking downstream.
    """
    deduplicated: List[Tuple[str, str]] = []
    seen = set()
    for url, title in results:
        normalized = normalize_url(url)
        if not normalized:
            continue
        comparison_key = normalized.rstrip("/").casefold()
        if comparison_key in seen:
            continue
        seen.add(comparison_key)
        deduplicated.append((normalized, str(title or "")))
        if len(deduplicated) >= limit:
            break
    return deduplicated


def _parse_html_results(raw_html: str, base_url: str, limit: int) -> List[Tuple[str, str]]:
    parser = _ResultLinkParser()
    try:
        parser.feed(raw_html)
        parser.close()
    except Exception as exc:
        print(f"WARN: could not parse search HTML: {exc}")
        return []

    candidates: List[Tuple[str, str]] = []
    for href, visible_text in parser.links:
        result_url = _normalize_result_url(href, base_url)
        if result_url:
            candidates.append((result_url, visible_text))
    return _deduplicate(candidates, limit)


def _search_duckduckgo_html(query: str, limit: int) -> List[Tuple[str, str]]:
    raw_html = _http_post(DUCKDUCKGO_HTML_URL, {"q": query, "kl": "us-en"})
    if not raw_html:
        return []
    if _looks_blocked(raw_html):
        print("WARN: DuckDuckGo HTML returned a challenge or rate-limit page.")
        return []
    return _parse_html_results(raw_html, DUCKDUCKGO_HTML_URL, limit)


def _search_duckduckgo_lite(query: str, limit: int) -> List[Tuple[str, str]]:
    raw_html = _http_get(DUCKDUCKGO_LITE_URL, {"q": query, "kl": "us-en"})
    if not raw_html:
        return []
    if _looks_blocked(raw_html):
        print("WARN: DuckDuckGo Lite returned a challenge or rate-limit page.")
        return []
    return _parse_html_results(raw_html, DUCKDUCKGO_LITE_URL, limit)


def _search_bing_html(query: str, limit: int) -> List[Tuple[str, str]]:
    """Scrape Bing's plain organic HTML results page.

    Bing dropped its public format=rss output for organic web search;
    requesting it can silently fall back to an unrelated dictionary
    vertical instead of real results. Scraping the normal HTML results
    page -- same technique as the DuckDuckGo providers above -- is the
    reliable, dependency-free option instead.
    """
    raw_html = _http_get(
        BING_SEARCH_URL, {"q": query, "count": "10", "setlang": "en-US", "mkt": "en-US"},
    )
    if not raw_html:
        return []
    if _looks_blocked(raw_html):
        print("WARN: Bing returned a challenge or rate-limit page.")
        return []
    return _parse_html_results(raw_html, BING_SEARCH_URL, limit)


# -----------------------------------------------------------------------
# Mojeek / Brave Search / Startpage
# -----------------------------------------------------------------------
# Implemented directly in this file rather than a companion module --
# a previous split caused a real startup crash when a companion module
# existed on disk but was accidentally left empty, and this module's
# top-level import from it raised ImportError before the app could even
# start. Keeping every provider in one file means there's nothing else
# that needs to exist and nothing else to keep in sync.

_CHROME_HOST_FRAGMENTS: Tuple[str, ...] = (
    "help.", "support.", "accounts.", "account.", "login.",
    "static.", "cdn.", "assets.",
)

_CHALLENGE_MARKERS: Tuple[str, ...] = (
    "verify you are human", "unusual traffic", "are you a robot",
    "captcha", "access denied", "attention required",
    "checking your browser", "cf-challenge", "before you continue",
    "consent.google", "please enable cookies",
)


@dataclass
class WebResult:
    """One normalized search result from an extra provider.

    A small dataclass purely for readability at the call sites below;
    converted to this module's plain (url, title) tuple contract via
    _adapt_extra_provider() before merging with the other providers.
    """

    title: str
    url: str
    snippet: str = ""


@dataclass
class ProviderOutcome:
    """Result of one extra-provider attempt, with a debug note.

    `results` is empty on any failure (network error, challenge page,
    zero parsed results); callers treat that as "fall through to the
    next provider," same as the DuckDuckGo HTML/Lite handling.
    """

    results: List[WebResult] = field(default_factory=list)
    debug_note: str = ""


class _ResultLinkTextParser(HTMLParser):
    """Generic, markup-agnostic search-result link extractor.

    Collects every outbound <a href> together with its inner text (a
    title candidate) and a short run of trailing plain text (a snippet
    candidate). Deciding which of these are genuine results happens
    afterward in _extract_result_links() -- this class only records raw
    candidates.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._depth_in_skip = 0
        self.candidates: List[Tuple[str, str, str]] = []
        self._pending_href: Optional[str] = None
        self._pending_title = ""
        self._current_title_parts: List[str] = []
        self._trailing_text_parts: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if self._pending_href is not None:
                self._flush_pending()
            self._pending_href = href
            self._current_title_parts = []
        elif tag.lower() in ("script", "style", "noscript"):
            self._depth_in_skip += 1

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._pending_href is not None:
            self._pending_title = " ".join(self._current_title_parts).strip()
        if tag.lower() in ("script", "style", "noscript"):
            if self._depth_in_skip > 0:
                self._depth_in_skip -= 1

    def handle_data(self, data):
        if self._depth_in_skip:
            return
        cleaned = re.sub(r"\s+", " ", data).strip()
        if not cleaned:
            return
        if self._pending_href is not None and not self._pending_title:
            self._current_title_parts.append(cleaned)
        else:
            self._trailing_text_parts.append(cleaned)
        if len(self._trailing_text_parts) > 40:
            self._flush_pending()

    def _flush_pending(self):
        if self._pending_href:
            snippet = " ".join(self._trailing_text_parts[:40]).strip()
            self.candidates.append((self._pending_href, self._pending_title, snippet))
        self._pending_href = None
        self._pending_title = ""
        self._trailing_text_parts = []

    def close(self):
        self._flush_pending()
        super().close()


def _looks_like_challenge_page(raw_html: str) -> bool:
    """Heuristically detect a bot-challenge/consent page."""
    prefix = raw_html[:4000].casefold()
    return any(marker in prefix for marker in _CHALLENGE_MARKERS)


def _is_chrome_link(candidate_host: str, engine_host: str) -> bool:
    """True when a link is the engine's own site chrome, not a result."""
    if not candidate_host:
        return True
    if candidate_host == engine_host or candidate_host.endswith("." + engine_host):
        return True
    return any(fragment in candidate_host for fragment in _CHROME_HOST_FRAGMENTS)


def _extract_result_links(raw_html: str, engine_host: str, limit: int) -> List[WebResult]:
    """Pull likely external result links out of a fetched results page.

    See the module docstring for why this avoids hardcoded CSS
    selectors. Deduplicates by URL and stops once `limit` results have
    been collected.
    """
    parser = _ResultLinkTextParser()
    try:
        parser.feed(raw_html)
        parser.close()
    except Exception:
        return []

    results: List[WebResult] = []
    seen_urls = set()
    for href, title, snippet in parser.candidates:
        if not href or not href.startswith(("http://", "https://")):
            continue
        parsed = urllib.parse.urlparse(href)
        host = parsed.netloc.casefold()
        if _is_chrome_link(host, engine_host):
            continue
        normalized_url = href.split("#", 1)[0]
        if normalized_url in seen_urls:
            continue
        display_title = title.strip() or host
        if len(display_title) < 2:
            continue
        seen_urls.add(normalized_url)
        results.append(WebResult(title=display_title, url=normalized_url, snippet=snippet.strip()))
        if len(results) >= limit:
            break
    return results


def _fetch_extra_provider(url: str) -> str:
    """Fetch a URL's raw HTML with a realistic browser User-Agent."""
    request = urllib.request.Request(url, headers=_request_headers())
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        raw_bytes = response.read(MAX_PAGE_BYTES + 1)
    if len(raw_bytes) > MAX_PAGE_BYTES:
        raise ValueError("search response exceeded maximum size")
    return raw_bytes.decode("utf-8", errors="replace")


def _run_extra_provider(provider_label: str, search_url: str, engine_host: str, limit: int) -> ProviderOutcome:
    """Shared fetch/challenge-detect/parse flow for one extra provider."""
    try:
        raw_html = _fetch_extra_provider(search_url)
    except urllib.error.HTTPError as exc:
        return ProviderOutcome(debug_note=f"WARN: {provider_label} returned HTTP {exc.code}.")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return ProviderOutcome(debug_note=f"WARN: {provider_label} request failed ({exc}).")
    except ValueError as exc:
        return ProviderOutcome(debug_note=f"WARN: {provider_label} request failed ({exc}).")

    if _looks_like_challenge_page(raw_html):
        return ProviderOutcome(
            debug_note=f"WARN: {provider_label} returned a challenge or consent page."
        )

    results = _extract_result_links(raw_html, engine_host, limit)
    if not results:
        return ProviderOutcome(
            debug_note=(
                f"WARN: {provider_label} returned no usable results "
                f"(fetched {len(raw_html)} chars)."
            )
        )

    return ProviderOutcome(results=results, debug_note=f"{provider_label}: {len(results)} result(s) parsed.")


def _mojeek_provider(query: str, limit: int = 5) -> ProviderOutcome:
    """Search Mojeek (mojeek.com), an independent, script-light index."""
    encoded_query = urllib.parse.quote_plus(query)
    search_url = f"{MOJEEK_SEARCH_URL}?q={encoded_query}"
    return _run_extra_provider("Mojeek", search_url, "www.mojeek.com", limit)


def _brave_provider(query: str, limit: int = 5) -> ProviderOutcome:
    """Search Brave Search (search.brave.com). High risk of blocking."""
    encoded_query = urllib.parse.quote_plus(query)
    search_url = f"{BRAVE_SEARCH_URL}?q={encoded_query}"
    return _run_extra_provider("Brave Search", search_url, "search.brave.com", limit)


def _startpage_provider(query: str, limit: int = 5) -> ProviderOutcome:
    """Search Startpage (startpage.com). Highest risk of blocking."""
    encoded_query = urllib.parse.quote_plus(query)
    search_url = f"{STARTPAGE_SEARCH_URL}?query={encoded_query}"
    return _run_extra_provider("Startpage", search_url, "www.startpage.com", limit)


def _adapt_extra_provider(provider_fn, query: str, limit: int) -> List[Tuple[str, str]]:
    """Bridge a Mojeek/Brave/Startpage provider into this module's (url, title) contract.

    Every result is re-run through _normalize_result_url() so these
    providers get the same tracking-parameter stripping, search-host
    filtering, and dictionary blocklist check as DuckDuckGo/Bing/
    Wikipedia results.
    """
    outcome = provider_fn(query, limit=limit)
    if outcome.debug_note and not outcome.results:
        print(outcome.debug_note)
    if not outcome.results:
        return []

    normalized: List[Tuple[str, str]] = []
    for result in outcome.results:
        cleaned_url = _normalize_result_url(result.url, result.url)
        if cleaned_url:
            normalized.append((cleaned_url, result.title))
    return normalized


def _search_startpage(query: str, limit: int) -> List[Tuple[str, str]]:
    """Tried first: most aggressive bot-detection, least-documented markup."""
    return _adapt_extra_provider(_startpage_provider, query, limit)


def _search_brave(query: str, limit: int) -> List[Tuple[str, str]]:
    """Tried second: heavy bot-detection and frequently-changing markup."""
    return _adapt_extra_provider(_brave_provider, query, limit)


def _search_mojeek(query: str, limit: int) -> List[Tuple[str, str]]:
    """Independent index, historically the most scraper-tolerant of the six HTML providers."""
    return _adapt_extra_provider(_mojeek_provider, query, limit)


def _search_wikipedia_api(query: str, limit: int) -> List[Tuple[str, str]]:
    """Search Wikipedia through its documented public JSON API.

    Runs last as a floor on quality -- a stable, key-free endpoint that
    keeps working under exactly the conditions that break the scrapers
    above it, at the cost of covering only encyclopedic topics.
    """
    request_url = WIKIPEDIA_API_URL + "?" + urllib.parse.urlencode(
        {
            "action": "query", "list": "search", "srsearch": query,
            "srlimit": str(max(1, min(int(limit), 50))),
            "srnamespace": "0", "format": "json",
        }
    )
    request = urllib.request.Request(
        request_url,
        headers={
            "User-Agent": USER_AGENT, "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.8", "Connection": "close",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = json.loads(_read_response(response))
    except urllib.error.HTTPError as exc:
        print(f"WARN: Wikipedia API returned HTTP {exc.code}")
        return []
    except urllib.error.URLError as exc:
        print(f"WARN: Wikipedia API network error: {exc.reason}")
        return []
    except (ValueError, TypeError) as exc:
        print(f"WARN: Wikipedia API returned unreadable JSON: {exc}")
        return []
    except Exception as exc:
        print(f"WARN: Wikipedia API request failed: {exc}")
        return []

    try:
        matches = payload["query"]["search"]
    except (KeyError, TypeError):
        print("WARN: Wikipedia API response contained no search results.")
        return []

    candidates: List[Tuple[str, str]] = []
    for match in matches:
        if not isinstance(match, dict):
            continue
        title = str(match.get("title") or "").strip()
        if not title:
            continue
        article_url = WIKIPEDIA_ARTICLE_BASE + urllib.parse.quote(title.replace(" ", "_"), safe="")
        normalized = _normalize_result_url(article_url, WIKIPEDIA_ARTICLE_BASE)
        if normalized:
            candidates.append((normalized, title))
    return _deduplicate(candidates, limit)


def search_public_web(
    query: str, limit: int = 5, with_titles: bool = False,
) -> Union[List[str], List[Tuple[str, str]]]:
    """Search public providers and return normalized results.

    Default (`with_titles=False`) returns a plain list[str] of URLs, as
    before -- every existing caller keeps working unchanged. With
    `with_titles=True`, returns list[tuple[str, str]] of (url, title)
    pairs, preserving each provider's displayed anchor text --
    web/crawler.py uses this to fold a result's title into its
    relevance scoring alongside the URL.
    """
    cleaned_query = " ".join(str(query or "").split())
    if not cleaned_query:
        print("WARN: public web search received an empty query.")
        return []

    try:
        result_limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        result_limit = 5

    providers = (
        # Ordered from MOST likely to be blocked to LEAST likely -- see
        # module docstring.
        ("Startpage", _search_startpage),
        ("Brave Search", _search_brave),
        ("DuckDuckGo HTML", _search_duckduckgo_html),
        ("DuckDuckGo Lite", _search_duckduckgo_lite),
        ("Bing HTML", _search_bing_html),
        ("Mojeek", _search_mojeek),
        ("Wikipedia API", _search_wikipedia_api),
    )

    collected: List[Tuple[str, str]] = []
    for provider_name, provider in providers:
        remaining = result_limit - len(collected)
        if remaining <= 0:
            break

        print(f"WEB SEARCH: trying {provider_name}")
        try:
            provider_results = provider(cleaned_query, remaining)
        except Exception as exc:
            print(f"WARN: {provider_name} search failed: {exc}")
            continue

        if not provider_results:
            print(f"WARN: {provider_name} returned no usable results.")
            continue

        related_results, unrelated_results = _partition_related_results(cleaned_query, provider_results)
        if not related_results:
            print(
                f"WARN: {provider_name} returned {len(provider_results)} "
                "result(s) unrelated to the query (likely a throttled or "
                "decoy response); discarding them and trying the next "
                "provider."
            )
            continue
        if unrelated_results:
            print(
                f"WARN: {provider_name} returned {len(unrelated_results)} "
                f"result(s) with no shared vocabulary with the query out "
                f"of {len(provider_results)} total; dropping just those "
                f"and keeping the other {len(related_results)}."
            )
        provider_results = related_results

        print(f"WEB SEARCH: {provider_name} returned {len(provider_results)} usable result(s).")
        collected.extend(provider_results)
        collected = _deduplicate(collected, result_limit)

    if not collected:
        print("No usable public search results were returned by any available provider.")

    if with_titles:
        return list(collected)
    return [url for url, _title in collected]


__all__ = ["search_public_web"]
