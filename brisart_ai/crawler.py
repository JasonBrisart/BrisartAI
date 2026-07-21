"""Optional internet search and crawling."""

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

from .extractor import html_to_text
from .policy import RobotsCache, USER_AGENT
from .util import normalize_url, same_site, stable_hash

MAX_PAGE_BYTES = 2_000_000
REQUEST_TIMEOUT = 15
DEFAULT_DELAY_SECONDS = 1.0


@dataclasses.dataclass
class FetchResult:
    url: str
    status: int
    content_type: str
    title: str
    text: str
    links: List[str]
    error: str = ""


def fetch_url(url: str) -> FetchResult:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            status = getattr(resp, "status", 200)
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read(MAX_PAGE_BYTES + 1)
            if len(raw) > MAX_PAGE_BYTES:
                return FetchResult(url, status, content_type, "", "", [], "page too large")
            charset = resp.headers.get_content_charset() or "utf-8"
            decoded = raw.decode(charset, "replace")
            if "text/plain" in content_type:
                return FetchResult(url, status, content_type, url, decoded.strip(), [])
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return FetchResult(url, status, content_type, "", "", [], "unsupported content type")
            title, text, links = html_to_text(decoded, base_url=url)
            return FetchResult(url, status, content_type, title or url, text, links)
    except urllib.error.HTTPError as exc:
        return FetchResult(url, int(exc.code), "", "", "", [], f"HTTP {exc.code}")
    except Exception as exc:
        return FetchResult(url, 0, "", "", "", [], str(exc))


def search_public_web(query: str, limit: int = 5) -> List[str]:
    encoded = urllib.parse.urlencode({"q": query})
    url = "https://duckduckgo.com/html/?" + encoded
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw_html = resp.read(MAX_PAGE_BYTES).decode(resp.headers.get_content_charset() or "utf-8", "replace")
    except Exception:
        return []

    links = []
    for match in re.finditer(r'href="([^"]+)"', raw_html):
        href = html.unescape(match.group(1))
        if "uddg=" in href:
            parsed = urllib.parse.urlparse(href)
            params = urllib.parse.parse_qs(parsed.query)
            target = params.get("uddg", [""])[0]
            target = normalize_url(target)
        else:
            target = normalize_url(urllib.parse.urljoin(url, href))
        if not target.startswith(("http://", "https://")):
            continue
        host = urllib.parse.urlsplit(target).netloc.lower()
        if "duckduckgo.com" in host:
            continue
        if target not in links:
            links.append(target)
        if len(links) >= limit:
            break
    return links


def crawl_urls_to_index(urls: Sequence[str], index, limit: int = 20, depth: int = 0, delay: float = DEFAULT_DELAY_SECONDS, same_domain_only: bool = True) -> int:
    robots = RobotsCache()
    pending: "queue.Queue[Tuple[str, int, str]]" = queue.Queue()
    seen: Set[str] = set()
    for raw in urls:
        url = normalize_url(raw)
        if url:
            pending.put((url, 0, url))
            seen.add(url)

    crawled = 0
    while not pending.empty() and crawled < limit:
        url, level, root = pending.get()
        if not robots.allowed(url):
            print(f"SKIP robots.txt: {url}")
            continue
        print(f"WEB FETCH depth={level}: {url}")
        result = fetch_url(url)
        if result.error:
            print(f"  WARN: {result.error}")
        else:
            index.add_source(
                source_type="web",
                location=result.url,
                title=result.title,
                text=result.text,
                content_hash=stable_hash(result.text),
                size_bytes=len(result.text.encode("utf-8", "replace")),
                extension=".html",
            )
            crawled += 1
            print(f"  OK: {len(result.text)} chars, {len(result.links)} links")
            if level < depth:
                for link in result.links:
                    if same_domain_only and not same_site(root, link):
                        continue
                    if link not in seen:
                        seen.add(link)
                        pending.put((link, level + 1, root))
        time.sleep(delay)
    return crawled


def web_search_and_ingest(query: str, index, limit: int = 5, crawl_depth: int = 0) -> int:
    links = search_public_web(query, limit=limit)
    if not links:
        print("No public search results found or search provider unavailable.")
        return 0
    print("Search results:")
    for i, link in enumerate(links, 1):
        print(f"[{i}] {link}")
    return crawl_urls_to_index(links, index, limit=limit, depth=crawl_depth, same_domain_only=True)
