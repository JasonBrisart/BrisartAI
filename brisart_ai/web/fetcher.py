from __future__ import annotations

import urllib.error
import urllib.request

from brisart_ai.io.extractor import html_to_text
from brisart_ai.util import normalize_url
from brisart_ai.web.models import FetchResult
from brisart_ai.web.policy import USER_AGENT

MAX_PAGE_BYTES = 2_000_000
REQUEST_TIMEOUT = 15


def fetch_url(url: str) -> FetchResult:
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