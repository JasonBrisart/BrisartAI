"""
File: brisart_ai/web/policy.py

Purpose
-------
Internet-access safety policy: refuse local/private network destinations
outright, and honor robots.txt for every public host BrisartAI crawls
(cached per site so a host is never re-fetched twice in one run).

Communication / relationships
------------------------------
- brisart_ai/web/crawler.py: builds one RobotsCache() per crawl and
  calls .allowed(url) before every fetch.
- brisart_ai/web/fetcher.py and brisart_ai/web/search.py: both import
  USER_AGENT from here, so every outbound request in the whole codebase
  carries the same, version-stamped identifier.
- Imports brisart_ai.version_info.__version__ to build USER_AGENT.

Settings / parameters
----------------------
- USER_AGENT: "BrisartAI/{__version__} (local-first research assistant;
  respectful public-web crawler)" -- version-stamped via version_info.py.
- ROBOTS_TIMEOUT (8 seconds) / MAX_ROBOTS_BYTES (512,000): bound how
  long and how much of a robots.txt fetch is allowed to take.

Edge cases
----------
- The important design decision: if robots.txt is missing, unreachable,
  too large, malformed, or returns 401/403 (read as "we can't tell what
  the policy is," not "this request is denied"), crawling is ALLOWED,
  not blocked. A retrieval failure must never be read as an explicit
  site-wide denial -- otherwise one flaky DNS hiccup would silently
  block an entire domain for the rest of the run. The only path that can
  genuinely deny a URL is a robots.txt that was successfully fetched,
  parsed, and explicitly disallows this user agent for that specific
  path.
- is_local_or_private_host() recognizes localhost and its variants,
  .local/.localhost suffixed hosts, and any IP address ipaddress
  classifies as private/loopback/link-local/multicast/reserved/
  unspecified -- this check runs before any network access at all.
- RobotsCache caches a None value (meaning "no parser, allow") just as
  readily as a real parsed RobotFileParser, so a site whose robots.txt
  failed once is not re-fetched again within the same run.
"""
from __future__ import annotations

import ipaddress
import threading
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from typing import Dict, Optional

from brisart_ai.version_info import __version__

USER_AGENT = (
    f"BrisartAI/{__version__} "
    "(local-first research assistant; respectful public-web crawler)"
)

ROBOTS_TIMEOUT = 8
MAX_ROBOTS_BYTES = 512_000


def is_local_or_private_host(hostname: str) -> bool:
    """Return True when a hostname points to a local/private address."""
    host = str(hostname or "").strip().casefold().strip("[]")
    if not host:
        return True
    if host in {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}:
        return True
    if host.endswith(".localhost") or host.endswith(".local"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        )
    )


def is_localhost(hostname: str) -> bool:
    """Compatibility alias for older BrisartAI imports."""
    return is_local_or_private_host(hostname)


class RobotsCache:
    """Fetch and cache robots.txt rules.

    Local/private destinations are always rejected. If a public site's
    robots.txt explicitly rejects the BrisartAI user agent, the URL is
    rejected. Anything else (missing, unreachable, malformed, or an
    ordinary error response) allows crawling -- see the module docstring
    for why a retrieval failure must never read as a denial.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}
        self._lock = threading.Lock()

    def _site_root(self, url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        return urllib.parse.urlunsplit((parsed.scheme.casefold(), parsed.netloc, "", "", ""))

    def _fetch_parser(self, site_root: str) -> Optional[urllib.robotparser.RobotFileParser]:
        robots_url = site_root.rstrip("/") + "/robots.txt"
        request = urllib.request.Request(
            robots_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/plain,*/*;q=0.1",
                "Connection": "close",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=ROBOTS_TIMEOUT) as response:
                raw = response.read(MAX_ROBOTS_BYTES + 1)
                if len(raw) > MAX_ROBOTS_BYTES:
                    print(f"WARN: robots.txt too large, allowing fetch: {robots_url}")
                    return None
                charset = response.headers.get_content_charset() or "utf-8"
                text = raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                print(
                    f"WARN: robots.txt returned HTTP {exc.code}; "
                    f"treating it as unavailable: {robots_url}"
                )
            elif exc.code not in {404, 410}:
                print(
                    f"WARN: robots.txt returned HTTP {exc.code}; "
                    f"allowing fetch: {robots_url}"
                )
            return None
        except urllib.error.URLError as exc:
            print(f"WARN: robots.txt unavailable, allowing fetch: {robots_url} ({exc.reason})")
            return None
        except Exception as exc:
            print(f"WARN: robots.txt check failed, allowing fetch: {robots_url} ({exc})")
            return None

        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        try:
            parser.parse(text.splitlines())
        except Exception as exc:
            print(f"WARN: robots.txt could not be parsed, allowing fetch: {robots_url} ({exc})")
            return None
        return parser

    def allowed(self, url: str) -> bool:
        """Return whether BrisartAI may fetch a public URL."""
        try:
            parsed = urllib.parse.urlsplit(str(url or "").strip())
        except ValueError:
            return False

        if parsed.scheme.casefold() not in {"http", "https"}:
            return False

        hostname = parsed.hostname or ""
        if is_local_or_private_host(hostname):
            print(f"SKIP local/private destination: {url}")
            return False

        site_root = self._site_root(url)
        with self._lock:
            if site_root not in self._cache:
                self._cache[site_root] = self._fetch_parser(site_root)
            parser = self._cache[site_root]

        if parser is None:
            return True

        try:
            return bool(parser.can_fetch(USER_AGENT, url))
        except Exception as exc:
            print(f"WARN: robots.txt decision failed, allowing fetch: {url} ({exc})")
            return True


__all__ = [
    "MAX_ROBOTS_BYTES",
    "ROBOTS_TIMEOUT",
    "RobotsCache",
    "USER_AGENT",
    "is_local_or_private_host",
    "is_localhost",
]
