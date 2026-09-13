"""
File: brisart_ai/web/models.py

Purpose
-------
Defines FetchResult, the single return value of one URL fetch attempt.
web/fetcher.py constructs it; web/crawler.py reads it to decide whether
a page gets indexed, skipped as empty, or logged as a failure.

Communication / relationships
------------------------------
- brisart_ai/web/fetcher.py: constructs FetchResult on every fetch_url()
  call, on both the success and failure paths.
- brisart_ai/web/crawler.py: reads .error/.text/.links/.title/.url off
  the FetchResult returned by fetch_url() inside crawl_urls_to_index().
- Imports nothing from elsewhere in brisart_ai; only dataclasses/typing.

Settings / parameters
----------------------
- url, status, content_type: the request's final normalized URL, the
  HTTP status code (0 if the request never reached the server), and the
  server's declared Content-Type.
- title, text, links: the page's extracted title, extracted body text,
  and outbound http(s) links discovered in the page (all empty when the
  fetch failed before extraction could run).
- error: empty string on success; a short human-readable failure reason
  otherwise (e.g. "HTTP 404", "network error: ...", "page too large").

Edge cases
----------
- A non-empty error does not guarantee every other field is blank --
  status may still carry a real HTTP code (e.g. 404) even on an error
  path, since status and error are set at different points during the
  fetch (status as soon as a response is received; error only if
  something afterward goes wrong).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class FetchResult:
    """Result of one public URL fetch."""

    url: str
    status: int
    content_type: str
    title: str
    text: str
    links: List[str]
    error: str = ""
