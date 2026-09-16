"""
File: brisart_ai/web/policy.py

Purpose
-------
Internet-access safety policy: refuse local/private network destinations
outright, and honor robots.txt for every public host BrisartAI crawls.

Communication / relationships
------------------------------
- brisart_ai/web/crawler.py: builds one RobotsCache() per crawl.
- brisart_ai/web/fetcher.py, brisart_ai/web/search.py: import USER_AGENT.
- Imports brisart_ai.version_info.__version__.
- Imports brisart_ai.native.brisart_url.brisart_urlsplit (replacing
  urllib.parse.urlsplit/urlunsplit) and brisart_ai.native.brisart_robots.
  BrisartRobotsPolicy (replacing urllib.robotparser.RobotFileParser) --
  see brisart_ai/native/README.md for verification. Actual HTTP requests
  (urllib.request/urllib.error) are unchanged.

Settings / parameters
----------------------
- USER_AGENT: version-stamped via version_info.py.
- ROBOTS_TIMEOUT (8s) / MAX_ROBOTS_BYTES (512,000).

Edge cases
----------
- Missing/unreachable/malformed robots.txt -> ALLOWED, not blocked.
- is_local_or_private_host() runs before any network access.
- BrisartRobotsPolicy mirrors urllib.robotparser's simpler algorithm.

Known limitations
-----------------
- Blocks localhost/private-range hosts to prevent SSRF, but the private-
  range check is IP/host-pattern based and cannot catch every rebinding
  or proxy trick.
- RobotsCache honors robots.txt with a bounded fetch (MAX_ROBOTS_BYTES,
  ROBOTS_TIMEOUT); an unreachable robots file is treated per the cache's
  fail policy, not re-tried aggressively.
- USER_AGENT is fixed; it does not rotate or masquerade.

Examples
--------
    >>> is_localhost("http://127.0.0.1:8000")
    True
    >>> is_local_or_private_host("http://10.0.0.5")
    True
    >>> is_local_or_private_host("https://example.com")
    False
"""
from __future__ import annotations

import ipaddress
import threading
import urllib.error
import urllib.request
from typing import Dict, Optional

from brisart_ai.native.brisart_robots import BrisartRobotsPolicy
from brisart_ai.native.brisart_url import brisart_urlsplit, brisart_urlunsplit
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
    return any((
        address.is_private, address.is_loopback, address.is_link_local,
        address.is_multicast, address.is_reserved, address.is_unspecified,
    ))


def is_localhost(hostname: str) -> bool:
    """Compatibility alias for older BrisartAI imports."""
    return is_local_or_private_host(hostname)


class RobotsCache:
    """Fetch and cache robots.txt rules."""

    def __init__(self) -> None:
        self._cache: Dict[str, Optional[BrisartRobotsPolicy]] = {}
        self._lock = threading.Lock()

    def _site_root(self, url: str) -> str:
        parsed = brisart_urlsplit(url)
        return brisart_urlunsplit(
            type(parsed)(parsed.scheme.casefold(), parsed.netloc, "", "", "")
        )

    def _fetch_parser(self, site_root: str) -> Optional[BrisartRobotsPolicy]:
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
                print(f"WARN: robots.txt returned HTTP {exc.code}; treating it as unavailable: {robots_url}")
            elif exc.code not in {404, 410}:
                print(f"WARN: robots.txt returned HTTP {exc.code}; allowing fetch: {robots_url}")
            return None
        except urllib.error.URLError as exc:
            print(f"WARN: robots.txt unavailable, allowing fetch: {robots_url} ({exc.reason})")
            return None
        except Exception as exc:
            print(f"WARN: robots.txt check failed, allowing fetch: {robots_url} ({exc})")
            return None

        parser = BrisartRobotsPolicy()
        try:
            parser.parse(text.splitlines())
        except Exception as exc:
            print(f"WARN: robots.txt could not be parsed, allowing fetch: {robots_url} ({exc})")
            return None
        return parser

    def allowed(self, url: str) -> bool:
        """Return whether BrisartAI may fetch a public URL."""
        try:
            parsed = brisart_urlsplit(str(url or "").strip())
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


__all__ = ["MAX_ROBOTS_BYTES", "ROBOTS_TIMEOUT", "RobotsCache", "USER_AGENT", "is_local_or_private_host", "is_localhost"]



