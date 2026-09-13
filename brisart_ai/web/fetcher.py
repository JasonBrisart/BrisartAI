"""
File: brisart_ai/web/fetcher.py

Purpose
-------
Single-URL retrieval: fetch one normalized URL, cap the response size,
decode using the declared/detected charset, and hand HTML off to
io/extractor.py's html_to_text() for a (title, text, links) triple.

Communication / relationships
------------------------------
- brisart_ai/web/crawler.py: the only caller of fetch_url(), inside
  crawl_urls_to_index().
- Calls brisart_ai.io.extractor.html_to_text() and
  brisart_ai.util.normalize_url(); imports USER_AGENT from
  brisart_ai.web.policy.

Settings / parameters
----------------------
- MAX_PAGE_BYTES (2,000,000): a response is read up to
  MAX_PAGE_BYTES + 1 bytes; if that many bytes came back, the page is
  rejected as too large rather than silently truncated and indexed with
  partial content.
- REQUEST_TIMEOUT (15 seconds): socket timeout for the fetch.
- Only text/plain, text/html, and application/xhtml+xml Content-Types
  are handled -- anything else (a PDF or image served directly over
  HTTP, say) is rejected outright, since PDF ingestion only applies to
  locally imported files via io/binary_readers.py, never to something
  fetched live from the web.

Edge cases
----------
- Every failure mode -- bad URL, oversized page, unsupported content
  type, HTTP error, network error -- is captured into the returned
  FetchResult rather than raised, so nobody needs a try/except around
  fetch_url().
- normalize_url("") or a URL that normalizes to an empty string returns
  a FetchResult with error="invalid URL" before any request is even
  attempted.
"""
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
            url=str(url), status=0, content_type="", title="", text="",
            links=[], error="invalid URL",
        )

    request = urllib.request.Request(
        normalized,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1"
            ),
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            status = int(getattr(response, "status", 200))
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(MAX_PAGE_BYTES + 1)

            if len(raw) > MAX_PAGE_BYTES:
                return FetchResult(
                    url=normalized, status=status, content_type=content_type,
                    title="", text="", links=[], error="page too large",
                )

            charset = response.headers.get_content_charset() or "utf-8"
            decoded = raw.decode(charset, errors="replace")

            lowered_type = content_type.casefold()
            if "text/plain" in lowered_type:
                return FetchResult(
                    url=normalized, status=status, content_type=content_type,
                    title=normalized, text=decoded.strip(), links=[],
                )

            if "text/html" not in lowered_type and "application/xhtml" not in lowered_type:
                return FetchResult(
                    url=normalized, status=status, content_type=content_type,
                    title="", text="", links=[], error="unsupported content type",
                )

            title, text, links = html_to_text(decoded, base_url=normalized)
            return FetchResult(
                url=normalized, status=status, content_type=content_type,
                title=title or normalized, text=text, links=links,
            )
    except urllib.error.HTTPError as exc:
        return FetchResult(
            url=normalized, status=int(exc.code), content_type="",
            title="", text="", links=[], error=f"HTTP {exc.code}",
        )
    except urllib.error.URLError as exc:
        return FetchResult(
            url=normalized, status=0, content_type="", title="", text="",
            links=[], error=f"network error: {exc.reason}",
        )
    except Exception as exc:
        return FetchResult(
            url=normalized, status=0, content_type="", title="", text="",
            links=[], error=str(exc),
        )
