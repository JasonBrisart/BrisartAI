from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request

from typing import List

from brisart_ai.util import normalize_url
from brisart_ai.web.policy import USER_AGENT
from brisart_ai.web.fetcher import (
    MAX_PAGE_BYTES,
    REQUEST_TIMEOUT,
)


def search_public_web(
    query: str,
    limit: int = 5,
) -> List[str]:
    """
    Search DuckDuckGo HTML results.

    Returns discovered public result URLs.
    """

    cleaned_query = str(
        query or ""
    ).strip()

    if not cleaned_query:
        return []

    try:
        result_limit = max(
            1,
            int(limit),
        )
    except (
        TypeError,
        ValueError,
    ):
        result_limit = 5

    encoded = urllib.parse.urlencode(
        {
            "q": cleaned_query,
        }
    )

    search_url = (
        "https://duckduckgo.com/html/?"
        + encoded
    )

    request = urllib.request.Request(
        search_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,"
                "*/*;q=0.8"
            ),
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

            raw_html = (
                response.read(
                    MAX_PAGE_BYTES
                )
                .decode(
                    charset,
                    errors="replace",
                )
            )

    except Exception:
        return []

    links: List[str] = []

    for match in re.finditer(
        r'href=[^"\']+["\']',
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

            parameters = (
                urllib.parse.parse_qs(
                    parsed.query
                )
            )

            target = parameters.get(
                "uddg",
                [""],
            )[0]

            target = normalize_url(
                target
            )

        else:
            target = normalize_url(
                urllib.parse.urljoin(
                    search_url,
                    href,
                )
            )

        if not target:
            continue

        if not target.startswith(
            (
                "http://",
                "https://",
            )
        ):
            continue

        host = (
            urllib.parse.urlsplit(
                target
            )
            .netloc
            .casefold()
        )

        if "duckduckgo.com" in host:
            continue

        if target not in links:
            links.append(
                target
            )

        if len(links) >= result_limit:
            break

    return links


__all__ = [
    "search_public_web",
]