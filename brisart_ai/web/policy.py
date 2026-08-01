"""Internet access and robots.txt policy helpers for BrisartAI."""

from __future__ import annotations

import ipaddress
import threading
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from typing import Dict, Optional

from brisart_ai import __version__


USER_AGENT = (
    f"BrisartAI/{__version__} "
    "(local-first research assistant; respectful public-web crawler)"
)

# Search-engine front ends serve a *degraded* results page to unknown
# bot user agents: DuckDuckGo HTML/Lite return an "Unfortunately, bots
# use DuckDuckGo too" anomaly challenge (zero results), and Bing quietly
# swaps the real organic results for a dictionary/glossary vertical -- so
# "how many cats are in america" came back as ten definitions of the
# word "many". Requesting those endpoints with a normal browser UA
# returns the genuine organic results.
#
# This is used ONLY for the search-provider requests in web/search.py.
# Actual page crawling in web/fetcher.py keeps the honest BrisartAI
# USER_AGENT above so crawled sites can still identify and robots-block
# us correctly.
SEARCH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

ROBOTS_TIMEOUT = 8
MAX_ROBOTS_BYTES = 512_000


def is_local_or_private_host(hostname: str) -> bool:
    """Return True when a hostname points to a local/private address."""

    host = str(hostname or "").strip().casefold().strip("[]")

    if not host:
        return True

    if host in {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
    }:
        return True

    if host.endswith(".localhost"):
        return True

    if host.endswith(".local"):
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

    Local and private destinations are always rejected.

    If a public site's robots.txt explicitly rejects the BrisartAI user
    agent, the URL is rejected.

    If robots.txt is missing, unreachable, malformed, or returns an
    ordinary error response, crawling is allowed. A retrieval failure
    must not be interpreted as an explicit site-wide denial.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}
        self._lock = threading.Lock()

    def _site_root(self, url: str) -> str:
        parsed = urllib.parse.urlsplit(url)

        return urllib.parse.urlunsplit(
            (
                parsed.scheme.casefold(),
                parsed.netloc,
                "",
                "",
                "",
            )
        )

    def _fetch_parser(
        self,
        site_root: str,
    ) -> Optional[urllib.robotparser.RobotFileParser]:
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
            with urllib.request.urlopen(
                request,
                timeout=ROBOTS_TIMEOUT,
            ) as response:
                raw = response.read(MAX_ROBOTS_BYTES + 1)

                if len(raw) > MAX_ROBOTS_BYTES:
                    print(
                        f"WARN: robots.txt too large, allowing fetch: "
                        f"{robots_url}"
                    )
                    return None

                charset = (
                    response.headers.get_content_charset()
                    or "utf-8"
                )

                text = raw.decode(
                    charset,
                    errors="replace",
                )

        except urllib.error.HTTPError as exc:
            if exc.code in {
                401,
                403,
            }:
                print(
                    f"WARN: robots.txt returned HTTP {exc.code}; "
                    f"treating it as unavailable: {robots_url}"
                )
            elif exc.code not in {
                404,
                410,
            }:
                print(
                    f"WARN: robots.txt returned HTTP {exc.code}; "
                    f"allowing fetch: {robots_url}"
                )

            return None

        except urllib.error.URLError as exc:
            print(
                f"WARN: robots.txt unavailable, allowing fetch: "
                f"{robots_url} ({exc.reason})"
            )
            return None

        except Exception as exc:
            print(
                f"WARN: robots.txt check failed, allowing fetch: "
                f"{robots_url} ({exc})"
            )
            return None

        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)

        try:
            parser.parse(text.splitlines())
        except Exception as exc:
            print(
                f"WARN: robots.txt could not be parsed, allowing fetch: "
                f"{robots_url} ({exc})"
            )
            return None

        return parser

    def allowed(self, url: str) -> bool:
        """Return whether BrisartAI may fetch a public URL."""

        try:
            parsed = urllib.parse.urlsplit(
                str(url or "").strip()
            )
        except ValueError:
            return False

        if parsed.scheme.casefold() not in {
            "http",
            "https",
        }:
            return False

        hostname = parsed.hostname or ""

        if is_local_or_private_host(hostname):
            print(
                f"SKIP local/private destination: {url}"
            )
            return False

        site_root = self._site_root(url)

        with self._lock:
            if site_root not in self._cache:
                self._cache[site_root] = self._fetch_parser(
                    site_root
                )

            parser = self._cache[site_root]

        if parser is None:
            return True

        try:
            return bool(
                parser.can_fetch(
                    USER_AGENT,
                    url,
                )
            )
        except Exception as exc:
            print(
                f"WARN: robots.txt decision failed, allowing fetch: "
                f"{url} ({exc})"
            )
            return True


__all__ = [
    "MAX_ROBOTS_BYTES",
    "ROBOTS_TIMEOUT",
    "RobotsCache",
    "SEARCH_USER_AGENT",
    "USER_AGENT",
    "is_local_or_private_host",
    "is_localhost",
]