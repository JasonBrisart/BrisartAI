"""Text extraction helpers."""

from __future__ import annotations

import html
import re
import urllib.parse
from html.parser import HTMLParser
from typing import List, Optional, Tuple

from .util import normalize_url


class HTMLTextExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas", "template"}
    BLOCK_TAGS = {"p", "div", "section", "article", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self, base_url: str = ""):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: List[str] = []
        self.text_parts: List[str] = []
        self.links: List[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href and self.base_url:
                link = normalize_url(urllib.parse.urljoin(self.base_url, href))
                if link.startswith(("http://", "https://")):
                    self.links.append(link)
        if tag in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        data = html.unescape(data).strip()
        if not data:
            return
        if self._in_title:
            self.title_parts.append(data)
        self.text_parts.append(data + " ")

    def result(self):
        title = " ".join(self.title_parts).strip()
        text = " ".join(self.text_parts)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n", text).strip()
        links = []
        seen = set()
        for link in self.links:
            if link not in seen:
                seen.add(link)
                links.append(link)
        return title, text, links


def html_to_text(source: str, base_url: str = ""):
    parser = HTMLTextExtractor(base_url=base_url)
    parser.feed(source)
    return parser.result()


def csv_to_text(source: str) -> str:
    lines = []
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = line.replace(",", " | ")
        lines.append(line)
    return "\n".join(lines)
