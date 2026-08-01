"""Dependency-free public web search for BrisartAI.

Searches multiple public endpoints without API keys:

1. DuckDuckGo HTML   (scraped)
2. DuckDuckGo Lite   (scraped)
3. Bing HTML         (scraped)
4. Wikipedia API     (real JSON API, no key)

Providers are attempted in order. Only organic search-result links are
extracted; results are normalized, deduplicated, and filtered before
being returned to the crawler.

The first three providers are HTML scrapers and therefore fragile: when
they detect automated traffic, DuckDuckGo serves an anti-bot challenge
and Bing rate-limits or substitutes an unrelated dictionary vertical. In
that state every scraper returns zero results and a question would
otherwise produce no sources at all. The Wikipedia API runs last as a
floor on quality -- it is a documented, stable, key-free endpoint that
keeps working under exactly those conditions, at the cost of covering
only encyclopedic topics.

Dictionary/definition-site blocking uses the shared list in
brisart_ai/blocklist.py, so search.py, crawler.py, and index.py all
agree on which hosts to reject (previously each kept its own copy and
they had drifted out of sync).
"""

from __future__ import annotations

import base64
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Dict, List, Optional, Sequence, Tuple

from brisart_ai.blocklist import is_blocked_web_host
from brisart_ai.util import normalize_url
from brisart_ai.web.fetcher import MAX_PAGE_BYTES, REQUEST_TIMEOUT
from brisart_ai.web.policy import USER_AGENT

DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"
DUCKDUCKGO_LITE_URL = "https://lite.duckduckgo.com/lite/"
BING_SEARCH_URL = "https://www.bing.com/search"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_ARTICLE_BASE = "https://en.wikipedia.org/wiki/"

_BLOCK_MARKERS = (
    "anomaly-modal",
    "anomaly.js",
    "bots use duckduckgo",
    "captcha",
    "challenge-form",
    "detected unusual traffic",
    "human verification",
    "operation timed out",
    "rate limit",
    "ratelimit",
    "too many requests",
)

_SEARCH_HOSTS = {
    "duckduckgo.com",
    "html.duckduckgo.com",
    "lite.duckduckgo.com",
    "www.duckduckgo.com",
    "bing.com",
    "www.bing.com",
    "cc.bingj.com",
    "go.microsoft.com",
    "login.live.com",
    "account.microsoft.com",
    "support.microsoft.com",
    "r.bing.com",
}

_IGNORED_SCHEMES = (
    "javascript:",
    "mailto:",
    "tel:",
    "data:",
)

# CSS classes that mark an anchor as an *organic* search result link
# rather than page chrome, navigation, ads, dictionary widgets, "people
# also ask", related searches, or footer links. Grabbing every anchor on
# a results page is what caused BrisartAI to ingest dictionary-definition
# widgets (e.g. results for the word "many") instead of the real answers.
_RESULT_LINK_CLASSES = (
    "result__a",       # DuckDuckGo HTML organic result title
    "result-link",     # DuckDuckGo Lite organic result title
    "result__url",     # DuckDuckGo HTML visible URL anchor
)

# Header tags that wrap organic result titles on providers (notably
# Bing) where the result anchor itself carries no distinctive class.
_RESULT_TITLE_TAGS = (
    "h2",
    "h3",
)


class _ResultLinkParser(HTMLParser):
    """Collect only *organic search result* anchor URLs.

    An anchor is treated as an organic result when either:

    * its ``class`` attribute matches a known result-link class
      (DuckDuckGo HTML / Lite), or
    * it is nested inside an ``<h2>``/``<h3>`` result-title heading
      (Bing, and DuckDuckGo fallbacks).

    Everything else on the page -- navigation, ads, sidebars, dictionary
    or knowledge-panel widgets, "people also ask", related searches, and
    footer links -- is ignored.
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
            classes = {
                token.casefold()
                for token in value.split()
            }
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
            text = " ".join(
                part.strip()
                for part in self._current_text
                if part.strip()
            )
            self.links.append(
                (
                    self._current_href,
                    text,
                )
            )
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
    return raw.decode(
        charset,
        errors="replace",
    )


def _http_get(
    url: str,
    parameters: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    request_url = url
    if parameters:
        encoded = urllib.parse.urlencode(parameters)
        separator = "&" if "?" in request_url else "?"
        request_url = f"{request_url}{separator}{encoded}"
    request = urllib.request.Request(
        request_url,
        headers=_request_headers(),
        method="GET",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT,
        ) as response:
            return _read_response(response)
    except urllib.error.HTTPError as exc:
        print(
            f"WARN: search provider returned HTTP {exc.code}: "
            f"{request_url}"
        )
    except urllib.error.URLError as exc:
        print(
            f"WARN: search provider network error: "
            f"{exc.reason}"
        )
    except Exception as exc:
        print(
            f"WARN: search provider request failed: {exc}"
        )
    return None


def _http_post(
    url: str,
    parameters: Dict[str, str],
) -> Optional[str]:
    encoded = urllib.parse.urlencode(parameters).encode("utf-8")
    headers = _request_headers()
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    headers["Origin"] = "https://duckduckgo.com"
    headers["Referer"] = "https://duckduckgo.com/"
    request = urllib.request.Request(
        url,
        data=encoded,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT,
        ) as response:
            return _read_response(response)
    except urllib.error.HTTPError as exc:
        print(
            f"WARN: search provider returned HTTP {exc.code}: "
            f"{url}"
        )
    except urllib.error.URLError as exc:
        print(
            f"WARN: search provider network error: "
            f"{exc.reason}"
        )
    except Exception as exc:
        print(
            f"WARN: search provider request failed: {exc}"
        )
    return None


def _looks_blocked(raw_text: str) -> bool:
    lowered = str(raw_text or "").casefold()
    return any(
        marker in lowered
        for marker in _BLOCK_MARKERS
    )


def _results_look_unrelated(
    query: str,
    results: Sequence[Tuple[str, str]],
) -> bool:
    """True when a provider's results share no vocabulary with the query.

    A rate-limited scraping provider does not always answer with an
    obvious challenge page. Bing was observed returning well-formed
    result HTML for an entirely unrelated query: "who invented the
    transistor" came back as airline booking pages, "invented
    transistor" as giraffe forum threads, and another run as bubble-sort
    tutorials. :func:`_looks_blocked` cannot see this because the markup
    is valid and parsing succeeds, so the junk reached the index looking
    like genuine research sources.

    The signal is that not one result -- URL or displayed title --
    contains any meaningful term from the query. A single weak match is
    enough to pass, so this stays conservative: it is meant to catch a
    wholesale topic swap, not to second-guess ranking. Matching allows a
    singular stem ("cats" -> "cat") so /wiki/Cat_behavior counts as
    related to a query about cats. Batches are only judged when there
    are enough results for a total absence of matches to be meaningful.
    """
    from brisart_ai.blocklist import FUNCTION_WORDS

    terms = {
        word
        for word in re.findall(r"[a-z0-9]+", str(query or "").casefold())
        if len(word) > 3 and word not in FUNCTION_WORDS
    }
    if not terms or len(results) < 3:
        return False

    for url, title in results:
        haystack = f"{url} {title}".casefold()
        for term in terms:
            stem = term.rstrip("s")
            if term in haystack or (len(stem) >= 3 and stem in haystack):
                return False
    return True


def _is_search_host(hostname: str) -> bool:
    host = str(hostname or "").casefold().strip(".")
    if host in _SEARCH_HOSTS:
        return True
    return any(
        host.endswith("." + search_host)
        for search_host in _SEARCH_HOSTS
    )


def _remove_tracking_parameters(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return ""
    ignored_parameters = {
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "source",
        "utm_campaign",
        "utm_content",
        "utm_medium",
        "utm_source",
        "utm_term",
    }
    parameters = urllib.parse.parse_qsl(
        parsed.query,
        keep_blank_values=True,
    )
    cleaned_parameters = [
        (name, value)
        for name, value in parameters
        if name.casefold() not in ignored_parameters
    ]
    cleaned_query = urllib.parse.urlencode(
        cleaned_parameters,
        doseq=True,
    )
    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            cleaned_query,
            "",
        )
    )


def _decode_duckduckgo_target(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return ""
    if "duckduckgo.com" not in parsed.netloc.casefold():
        return url
    parameters = urllib.parse.parse_qs(
        parsed.query,
        keep_blank_values=True,
    )
    values = parameters.get("uddg")
    if not values:
        return url
    target = values[0]
    for _ in range(3):
        decoded = urllib.parse.unquote(target)
        if decoded == target:
            break
        target = decoded
    if target.startswith(("http://", "https://")):
        return target
    return url


def _decode_bing_target(url: str) -> str:
    """Unwrap Bing's ``/ck/a`` click-tracking redirect wrapper.

    Bing wraps organic result links as
    ``https://www.bing.com/ck/a?...&u=a1<base64url>&...`` where the
    ``u`` parameter's value is prefixed with an encoding tag (``a1``)
    followed by URL-safe base64 without padding. If unwrapping fails
    for any reason, the original URL is returned unchanged.
    """
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    if "bing.com" not in parsed.netloc.casefold():
        return url
    if not parsed.path.casefold().endswith("/ck/a"):
        return url
    parameters = urllib.parse.parse_qs(
        parsed.query,
        keep_blank_values=True,
    )
    values = parameters.get("u")
    if not values:
        return url
    encoded = values[0]
    if not encoded[2:]:
        return url
    # Bing prefixes the payload with a short encoding tag (commonly
    # "a1") before the base64url body.
    payload = encoded[2:] if len(encoded) > 2 else encoded
    padding = "=" * (-len(payload) % 4)
    try:
        decoded_bytes = base64.urlsafe_b64decode(payload + padding)
        decoded = decoded_bytes.decode("utf-8", errors="replace")
    except Exception:
        return url
    if decoded.startswith(("http://", "https://")):
        return decoded
    return url


def _strip_embedded_markup(text: str) -> str:
    """Best-effort extraction of an ``href`` value from stray HTML.

    Search result text should already be a bare URL. If a provider or
    an intermediary ever hands back an entire anchor tag as the value
    instead of just the URL (seen in the wild from some proxied or
    rewritten responses), pull the real destination out of the
    ``href="..."`` attribute rather than treating the whole markup
    blob as a URL.
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


def _normalize_result_url(
    href: str,
    base_url: str,
) -> str:
    candidate = html.unescape(
        _strip_embedded_markup(href)
    )
    if not candidate:
        return ""
    lowered = candidate.casefold()
    if lowered.startswith(_IGNORED_SCHEMES):
        return ""
    if candidate.startswith("//"):
        candidate = "https:" + candidate
    else:
        candidate = urllib.parse.urljoin(
            base_url,
            candidate,
        )
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


def _deduplicate(
    results: Sequence[Tuple[str, str]],
    limit: int,
) -> List[Tuple[str, str]]:
    """Deduplicate ``(url, title)`` result pairs, preserving order.

    Titles ride along with each URL so provider-level relevance checks
    can inspect the result text a provider actually displayed, not just
    the link target. Titles are dropped again at the public boundary in
    :func:`search_public_web`.
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
        deduplicated.append(
            (normalized, str(title or "")),
        )
        if len(deduplicated) >= limit:
            break
    return deduplicated


def _parse_html_results(
    raw_html: str,
    base_url: str,
    limit: int,
) -> List[Tuple[str, str]]:
    parser = _ResultLinkParser()
    try:
        parser.feed(raw_html)
        parser.close()
    except Exception as exc:
        print(
            f"WARN: could not parse search HTML: {exc}"
        )
        return []
    candidates: List[Tuple[str, str]] = []
    for href, visible_text in parser.links:
        result_url = _normalize_result_url(
            href,
            base_url,
        )
        if result_url:
            candidates.append(
                (result_url, visible_text),
            )
    return _deduplicate(
        candidates,
        limit,
    )


def _search_duckduckgo_html(
    query: str,
    limit: int,
) -> List[Tuple[str, str]]:
    raw_html = _http_post(
        DUCKDUCKGO_HTML_URL,
        {
            "q": query,
            "kl": "us-en",
        },
    )
    if not raw_html:
        return []
    if _looks_blocked(raw_html):
        print(
            "WARN: DuckDuckGo HTML returned a challenge or "
            "rate-limit page."
        )
        return []
    return _parse_html_results(
        raw_html,
        DUCKDUCKGO_HTML_URL,
        limit,
    )


def _search_duckduckgo_lite(
    query: str,
    limit: int,
) -> List[Tuple[str, str]]:
    raw_html = _http_get(
        DUCKDUCKGO_LITE_URL,
        {
            "q": query,
            "kl": "us-en",
        },
    )
    if not raw_html:
        return []
    if _looks_blocked(raw_html):
        print(
            "WARN: DuckDuckGo Lite returned a challenge or "
            "rate-limit page."
        )
        return []
    return _parse_html_results(
        raw_html,
        DUCKDUCKGO_LITE_URL,
        limit,
    )


def _search_bing_html(
    query: str,
    limit: int,
) -> List[Tuple[str, str]]:
    """Scrape Bing's plain organic HTML results page.

    Bing dropped its public ``format=rss`` output for organic web
    search some time ago; requesting it no longer returns real search
    results (it can silently fall back to an unrelated dictionary/
    glossary vertical instead). Scraping the normal HTML results page
    -- the same technique used for the DuckDuckGo providers above --
    is the reliable, dependency-free option instead.
    """
    raw_html = _http_get(
        BING_SEARCH_URL,
        {
            "q": query,
            "count": "10",
            "setlang": "en-US",
            "mkt": "en-US",
        },
    )
    if not raw_html:
        return []
    if _looks_blocked(raw_html):
        print(
            "WARN: Bing returned a challenge or rate-limit page."
        )
        return []
    return _parse_html_results(
        raw_html,
        BING_SEARCH_URL,
        limit,
    )


def _search_wikipedia_api(
    query: str,
    limit: int,
) -> List[Tuple[str, str]]:
    """Search Wikipedia through its documented public JSON API.

    This provider exists because every HTML-scraping provider above is a
    single anti-bot policy change away from returning nothing: DuckDuckGo
    answers automated requests with an "Unfortunately, bots use
    DuckDuckGo too" challenge page, and Bing rate-limits and can swap
    organic results for an unrelated dictionary vertical. When that
    happens to all of them at once, BrisartAI previously reported "no
    usable results" and indexed nothing at all.

    ``action=query&list=search`` is a real, stable, key-free API rather
    than a scraped page, so it keeps working under exactly the conditions
    that break the scrapers. It only covers encyclopedic topics, which is
    why it runs last -- as a floor on quality, not a replacement for
    general web search.

    Wikipedia's API asks for a descriptive User-Agent identifying the
    client, so this request deliberately uses the honest BrisartAI agent
    instead of the browser string used for the scraping providers.
    """
    request_url = WIKIPEDIA_API_URL + "?" + urllib.parse.urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": str(max(1, min(int(limit), 50))),
            "srnamespace": "0",
            "format": "json",
        }
    )
    request = urllib.request.Request(
        request_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.8",
            "Connection": "close",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT,
        ) as response:
            payload = json.loads(
                _read_response(response)
            )
    except urllib.error.HTTPError as exc:
        print(
            f"WARN: Wikipedia API returned HTTP {exc.code}"
        )
        return []
    except urllib.error.URLError as exc:
        print(
            f"WARN: Wikipedia API network error: {exc.reason}"
        )
        return []
    except (ValueError, TypeError) as exc:
        print(
            f"WARN: Wikipedia API returned unreadable JSON: {exc}"
        )
        return []
    except Exception as exc:
        print(
            f"WARN: Wikipedia API request failed: {exc}"
        )
        return []

    try:
        matches = payload["query"]["search"]
    except (KeyError, TypeError):
        print(
            "WARN: Wikipedia API response contained no search results."
        )
        return []

    candidates: List[Tuple[str, str]] = []
    for match in matches:
        if not isinstance(match, dict):
            continue
        title = str(match.get("title") or "").strip()
        if not title:
            continue
        article_url = WIKIPEDIA_ARTICLE_BASE + urllib.parse.quote(
            title.replace(" ", "_"),
            safe="",
        )
        normalized = _normalize_result_url(
            article_url,
            WIKIPEDIA_ARTICLE_BASE,
        )
        if normalized:
            candidates.append(
                (normalized, title),
            )
    return _deduplicate(
        candidates,
        limit,
    )


def search_public_web(
    query: str,
    limit: int = 5,
) -> List[str]:
    """Search public providers and return normalized result URLs."""
    cleaned_query = " ".join(
        str(query or "").split()
    )
    if not cleaned_query:
        print("WARN: public web search received an empty query.")
        return []
    try:
        result_limit = max(
            1,
            min(int(limit), 50),
        )
    except (TypeError, ValueError):
        result_limit = 5
    providers = (
        (
            "DuckDuckGo HTML",
            _search_duckduckgo_html,
        ),
        (
            "DuckDuckGo Lite",
            _search_duckduckgo_lite,
        ),
        (
            "Bing HTML",
            _search_bing_html,
        ),
        # Runs last: a key-free real API that still works when the
        # scraping providers above are challenged or rate-limited, so a
        # question returns encyclopedic sources instead of nothing.
        (
            "Wikipedia API",
            _search_wikipedia_api,
        ),
    )
    collected: List[Tuple[str, str]] = []
    for provider_name, provider in providers:
        remaining = result_limit - len(collected)
        if remaining <= 0:
            break
        print(
            f"WEB SEARCH: trying {provider_name}"
        )
        try:
            provider_results = provider(
                cleaned_query,
                remaining,
            )
        except Exception as exc:
            print(
                f"WARN: {provider_name} search failed: {exc}"
            )
            continue
        if not provider_results:
            print(
                f"WARN: {provider_name} returned no usable results."
            )
            continue
        if _results_look_unrelated(cleaned_query, provider_results):
            print(
                f"WARN: {provider_name} returned {len(provider_results)} "
                "result(s) unrelated to the query (likely a throttled or "
                "decoy response); discarding them and trying the next "
                "provider."
            )
            continue
        print(
            f"WEB SEARCH: {provider_name} returned "
            f"{len(provider_results)} usable result(s)."
        )
        collected.extend(provider_results)
        collected = _deduplicate(
            collected,
            result_limit,
        )
    if not collected:
        print(
            "No usable public search results were returned by any "
            "available provider."
        )
    # Titles exist only so provider-level relevance checks can inspect
    # displayed result text; callers still receive plain URLs.
    return [url for url, _title in collected]


__all__ = [
    "search_public_web",
]
