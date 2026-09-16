"""
File: brisart_ai/io/extractor.py

Purpose
-------
Two text-extraction helpers: html_to_text() and csv_to_text().
HTMLTextExtractor is a brisart_ai.native.brisart_markup.BrisartMarkupParser
subclass.

Communication / relationships
------------------------------
- brisart_ai/web/fetcher.py: calls html_to_text() on every fetched page.
- brisart_ai/io/readers.py: calls html_to_text()/csv_to_text().
- Imports brisart_ai.native.brisart_markup.BrisartMarkupParser (replacing
  html.parser.HTMLParser) and brisart_ai.native.brisart_url.brisart_urljoin()
  (replacing urllib.parse.urljoin()) -- see brisart_ai/native/README.md.

Settings / parameters
----------------------
- SKIP_TAGS / BLOCK_TAGS: tags never emitted as text / newline-boundary tags.
- REFERENCE_MARKER_TAGS / REFERENCE_MARKER_CLASSES: <sup> citation markers
  are skipped.

Edge cases
----------
- <sup class="reference">[3]</sup> is skipped, scoped narrowly to <sup>.
- csv_to_text() falls back to naive comma-to-pipe split on malformed CSV.
- html_to_text() wraps feed()/close() in try/except.

Known limitations
-----------------
- HTMLTextExtractor is a tolerant tag stripper, not a DOM/CSS engine; it
  drops scripts/styles and collapses whitespace but does not execute or
  layout anything.
- csv_to_text() assumes comma delimiting and flattens rows to lines; it
  does not sniff alternate delimiters or quoting dialects.
- No character-set auto-detection beyond what the caller provides.

Examples
--------
    >>> html_to_text("<p>Hello <b>world</b></p><script>x()</script>")
    'Hello world'
    >>> csv_to_text("a,b\n1,2")
    'a b\n1 2'
"""
from __future__ import annotations

import csv
import io
import re
from typing import List, Optional, Tuple

from brisart_ai.native.brisart_markup import BrisartMarkupParser, brisart_unescape
from brisart_ai.native.brisart_url import brisart_urljoin
from brisart_ai.util import normalize_url


class HTMLTextExtractor(BrisartMarkupParser):
    """Extract readable text, page titles, and links from HTML."""

    SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas", "template"}
    BLOCK_TAGS = {
        "p", "div", "section", "article", "aside", "header", "footer",
        "main", "nav", "br", "li", "ul", "ol", "table", "tr", "td",
        "th", "blockquote", "pre", "h1", "h2", "h3", "h4", "h5", "h6",
    }
    REFERENCE_MARKER_TAGS = {"sup"}
    REFERENCE_MARKER_CLASSES = {"reference", "cite-bracket", "citation"}

    def __init__(self, base_url: str = ""):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: List[str] = []
        self.text_parts: List[str] = []
        self.links: List[str] = []
        self._skip_depth = 0
        self._reference_skip_depth = 0
        self._in_title = False

    def _is_reference_marker(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> bool:
        if tag not in self.REFERENCE_MARKER_TAGS:
            return False
        for name, value in attrs:
            if name.casefold() != "class" or not value:
                continue
            classes = {token.casefold() for token in value.split()}
            if classes & self.REFERENCE_MARKER_CLASSES:
                return True
        return False

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if self._is_reference_marker(tag, attrs):
            self._reference_skip_depth += 1
            return
        if self._reference_skip_depth:
            return
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                absolute = brisart_urljoin(self.base_url, href)
                link = normalize_url(absolute)
                if link.startswith(("http://", "https://")):
                    self.links.append(link)
        if tag in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_startendtag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in self.REFERENCE_MARKER_TAGS and self._reference_skip_depth:
            self._reference_skip_depth -= 1
            return
        if self._reference_skip_depth:
            return
        if tag == "title":
            self._in_title = False
        if tag in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth or self._reference_skip_depth:
            return
        cleaned = brisart_unescape(data)
        cleaned = re.sub(r"[ \t\r\f\v]+", " ", cleaned).strip()
        if not cleaned:
            return
        if self._in_title:
            self.title_parts.append(cleaned)
        self.text_parts.append(cleaned + " ")

    def result(self) -> Tuple[str, str, List[str]]:
        title = " ".join(self.title_parts).strip()
        text = "".join(self.text_parts)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        unique_links: List[str] = []
        seen = set()
        for link in self.links:
            if link and link not in seen:
                seen.add(link)
                unique_links.append(link)
        return title, text, unique_links


def html_to_text(source: str, base_url: str = "") -> Tuple[str, str, List[str]]:
    """Convert HTML into a title, readable text, and discovered links."""
    parser = HTMLTextExtractor(base_url=base_url)
    try:
        parser.feed(source)
        parser.close()
    except Exception:
        pass
    return parser.result()


def csv_to_text(source: str) -> str:
    """Convert CSV text into searchable pipe-separated text."""
    output: List[str] = []
    try:
        reader = csv.reader(io.StringIO(source))
        for row in reader:
            cleaned = [cell.strip() for cell in row]
            if any(cleaned):
                output.append(" | ".join(cleaned))
        return "\n".join(output)
    except (csv.Error, UnicodeError):
        pass
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if line:
            output.append(line.replace(",", " | "))
    return "\n".join(output)


