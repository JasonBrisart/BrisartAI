"""Optional public-web search and crawling for BrisartAI."""

from __future__ import annotations

import dataclasses
import html
import queue
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import List, Sequence, Set, Tuple

from brisart_ai.io.extractor import html_to_text
from brisart_ai.util import (
    normalize_url,
    same_site,
    stable_hash,
)
from brisart_ai.web.policy import (
    RobotsCache,
    USER_AGENT,
)


MAX_PAGE_BYTES = 2_000_000
REQUEST_TIMEOUT = 15
DEFAULT_DELAY_SECONDS = 1.0


@dataclasses.dataclass
class FetchResult:
    """Result of one public URL fetch."""

    url: str
    status: int
    content_type: str
    title: str
    text: str
    links: List[str]
    error: str = ""


def fetch_url(
    url: str,
) -> FetchResult:
    """Fetch and extract text from one public URL."""

    normalized = normalize_url(url)

    if not normalized:
        return FetchResult(
            url=str(url),
            status=0,
            content_type="",
            title="",
            text="",
            links=[],
            error="invalid URL",
        )

    request = urllib.request.Request(
        normalized,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "text/plain;q=0.9,"
                "*/*;q=0.1"
            ),
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT,
        ) as response:
            status = int(
                getattr(response, "status", 200)
            )

            content_type = response.headers.get(
                "Content-Type",
                "",
            )

            raw = response.read(
                MAX_PAGE_BYTES + 1
            )

            if len(raw) > MAX_PAGE_BYTES:
                return FetchResult(
                    url=normalized,
                    status=status,
                    content_type=content_type,
                    title="",
                    text="",
                    links=[],
                    error="page too large",
                )

            charset = (
                response.headers.get_content_charset()
                or "utf-8"
            )

            decoded = raw.decode(
                charset,
                errors="replace",
            )

            lowered_type = content_type.casefold()

            if "text/plain" in lowered_type:
                return FetchResult(
                    url=normalized,
                    status=status,
                    content_type=content_type,
                    title=normalized,
                    text=decoded.strip(),
                    links=[],
                )

            if (
                "text/html" not in lowered_type
                and "application/xhtml" not in lowered_type
            ):
                return FetchResult(
                    url=normalized,
                    status=status,
                    content_type=content_type,
                    title="",
                    text="",
                    links=[],
                    error="unsupported content type",
                )

            title, text, links = html_to_text(
                decoded,
                base_url=normalized,
            )

            return FetchResult(
                url=normalized,
                status=status,
                content_type=content_type,
                title=title or normalized,
                text=text,
                links=links,
            )

    except urllib.error.HTTPError as exc:
        return FetchResult(
            url=normalized,
            status=int(exc.code),
            content_type="",
            title="",
            text="",
            links=[],
            error=f"HTTP {exc.code}",
        )

    except urllib.error.URLError as exc:
        return FetchResult(
            url=normalized,
            status=0,
            content_type="",
            title="",
            text="",
            links=[],
            error=f"network error: {exc.reason}",
        )

    except Exception as exc:
        return FetchResult(
            url=normalized,
            status=0,
            content_type="",
            title="",
            text="",
            links=[],
            error=str(exc),
        )


def search_public_web(
    query: str,
    limit: int = 5,
) -> List[str]:
    """Search public DuckDuckGo HTML results.

    Returns discovered public result URLs.
    """

    cleaned_query = str(query or "").strip()

    if not cleaned_query:
        return []

    try:
        result_limit = max(1, int(limit))
    except (TypeError, ValueError):
        result_limit = 5

    encoded = urllib.parse.urlencode(
        {"q": cleaned_query}
    )

    search_url = (
        "https://duckduckgo.com/html/?"
        + encoded
    )

    request = urllib.request.Request(
        search_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,*/*;q=0.8",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT,
        ) as response:
            charset = (
                response.headers.get_content_charset()
                or "utf-8"
            )

            raw_html = response.read(
                MAX_PAGE_BYTES
            ).decode(
                charset,
                errors="replace",
            )

    except Exception:
        return []

    links: List[str] = []

    for match in re.finditer(
        r'href=["\']([^"\']+)["\']',
        raw_html,
        flags=re.IGNORECASE,
    ):
        href = html.unescape(
            match.group(1)
        )

        if "uddg=" in href:
            parsed = urllib.parse.urlparse(
                href
            )

            parameters = urllib.parse.parse_qs(
                parsed.query
            )

            target = parameters.get(
                "uddg",
                [""],
            )[0]

            target = normalize_url(target)
        else:
            target = normalize_url(
                urllib.parse.urljoin(
                    search_url,
                    href,
                )
            )

        if not target.startswith(
            ("http://", "https://")
        ):
            continue

        host = urllib.parse.urlsplit(
            target
        ).netloc.casefold()

        if "duckduckgo.com" in host:
            continue

        if target not in links:
            links.append(target)

        if len(links) >= result_limit:
            break

    return links


def crawl_urls_to_index(
    urls: Sequence[str],
    index,
    limit: int = 20,
    depth: int = 0,
    delay: float = DEFAULT_DELAY_SECONDS,
    same_domain_only: bool = True,
) -> int:
    """Crawl public URLs and add extracted text to an index."""

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

    robots = RobotsCache()

    pending: queue.Queue[
        Tuple[str, int, str]
    ] = queue.Queue()

    seen: Set[str] = set()

    for raw_url in urls:
        normalized = normalize_url(raw_url)

        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)
        pending.put(
            (
                normalized,
                0,
                normalized,
            )
        )

    crawled = 0

    while (
        not pending.empty()
        and crawled < crawl_limit
    ):
        current_url, level, root_url = (
            pending.get()
        )

        if not robots.allowed(current_url):
            print(
                f"SKIP robots.txt: {current_url}"
            )
            continue

        print(
            f"WEB FETCH depth={level}: "
            f"{current_url}"
        )

        result = fetch_url(current_url)

        if result.error:
            print(
                f"  WARN: {result.error}"
            )
        elif not result.text.strip():
            print(
                "  WARN: page contained no "
                "extractable text"
            )
        else:
            indexed = index.add_source(
                source_type="web",
                location=result.url,
                title=result.title,
                text=result.text,
                content_hash=stable_hash(
                    result.text
                ),
                size_bytes=len(
                    result.text.encode(
                        "utf-8",
                        errors="replace",
                    )
                ),
                extension=".html",
            )

            if indexed:
                crawled += 1

                print(
                    f"  OK: {len(result.text)} chars, "
                    f"{len(result.links)} links"
                )

            if level < crawl_depth:
                for link in result.links:
                    normalized_link = normalize_url(
                        link
                    )

                    if not normalized_link:
                        continue

                    if (
                        same_domain_only
                        and not same_site(
                            root_url,
                            normalized_link,
                        )
                    ):
                        continue

                    if normalized_link in seen:
                        continue

                    seen.add(normalized_link)

                    pending.put(
                        (
                            normalized_link,
                            level + 1,
                            root_url,
                        )
                    )

        if crawl_delay:
            time.sleep(crawl_delay)

    return crawled


def web_search_and_ingest(
    query: str,
    index,
    limit: int = 5,
    crawl_depth: int = 0,
) -> int:
    """Search the public web and ingest retrieved pages."""

    links = search_public_web(
        query,
        limit=limit,
    )

    if not links:
        print(
            "No public search results found or "
            "the search provider was unavailable."
        )
        return 0

    print("Search results:")

    for number, link in enumerate(
        links,
        start=1,
    ):
        print(f"[{number}] {link}")

    return crawl_urls_to_index(
        links,
        index,
        limit=limit,
        depth=crawl_depth,
        same_domain_only=True,
    )


__all__ = [
    "DEFAULT_DELAY_SECONDS",
    "FetchResult",
    "fetch_url",
    "search_public_web",
    "crawl_urls_to_index",
    "web_search_and_ingest",
]
