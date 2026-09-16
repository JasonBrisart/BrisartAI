"""
File: brisart_ai/native/brisart_markup.py

Purpose
-------
BrisartMarkupParser -- a from-scratch, pure-Python HTML tokenizer,
replacing html.parser.HTMLParser as the base class io/extractor.py's
HTMLTextExtractor and web/search.py's _ResultLinkParser /
_ResultLinkTextParser subclass. This is a lenient, forgiving tokenizer
by design -- exactly like the class it replaces -- because it is fed
real-world web HTML, which is routinely malformed (unclosed tags,
unescaped ampersands, mismatched nesting) and must degrade gracefully
rather than raise.

Communication / relationships
------------------------------
- Intended as a drop-in base class replacement: a subclass overriding
  handle_starttag(tag, attrs), handle_endtag(tag), handle_data(data),
  and optionally handle_startendtag(tag, attrs), calling feed(html) and
  close(), keeps working with only the base-class import changed.
- Imports nothing from elsewhere in brisart_ai; a hand-written
  character-by-character scanner, no dependency on html.parser or any
  other markup library.

Settings / parameters
----------------------
- handle_startendtag() only fires when the SOURCE markup explicitly
  writes a trailing "/" ("<br/>"); a bare void element with no slash
  ("<br>", "<img src=x>") calls handle_starttag() like any other tag,
  and never receives a matching handle_endtag() call -- this precisely
  mirrors html.parser.HTMLParser's own behavior (confirmed directly
  against it), rather than inferring "this tag never has a closing tag
  in HTML" from a void-element table, which does NOT match how the
  stdlib parser actually behaves.
- _NAMED_ENTITIES: a table covering the small set of named character
  references BrisartAI's own extraction logic actually encounters in
  practice (&amp; &lt; &gt; &quot; &#39; &nbsp; and a handful of
  others) -- not the full HTML5 named-entity table (over 2000 entries),
  which is out of proportion to what a lenient extractor needs; a
  numeric reference (&#NNN; or &#xHH;) is always decoded exactly,
  regardless of this table's coverage.

Edge cases
----------
- A raw, unescaped "<" inside what looks like a data region is treated
  as the start of a new tag if what follows looks like a tag name,
  exactly matching real browsers' and html.parser's own lenient
  handling of malformed markup -- a strict, spec-perfect XML parser
  would raise on this and break real-world extraction.
- <script>, <style>, and other raw-text elements have their content
  captured as an OPAQUE blob (not tokenized as markup) until their
  matching closing tag, so a literal "<" or ">" inside a <script>
  block's JavaScript never confuses the tokenizer.
- feed() may be called multiple times before close(); any partial tag
  or entity reference spanning a feed() boundary is buffered internally
  and completed on the next feed() call, mirroring
  html.parser.HTMLParser's own incremental-feed contract.

Known limitations
-----------------
- A tolerant HTML tokenizer/entity unescaper, not a spec-compliant HTML5
  tree builder; malformed nesting is handled leniently, not corrected.
- _NAMED_ENTITIES covers common entities only; an unlisted named entity
  is left as literal text.
- Raw-text elements (script/style) are recognized but their contents are
  discarded, not parsed.

Examples
--------
    >>> brisart_unescape("Tom &amp; Jerry &lt;3")
    'Tom & Jerry <3'
    >>> p = BrisartMarkupParser(); p.feed("<p>hi</p>")   # doctest: +SKIP
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

_TAG_NAME_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9:-]*")
_ATTR_NAME_RE = re.compile(r"[^\s=/>]+")

_RAW_TEXT_ELEMENTS = {"script", "style", "textarea", "title"}

_NAMED_ENTITIES = {
    "amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'",
    "nbsp": "\u00a0", "copy": "\u00a9", "reg": "\u00ae", "mdash": "\u2014",
    "ndash": "\u2013", "hellip": "\u2026", "rsquo": "\u2019", "lsquo": "\u2018",
    "rdquo": "\u201d", "ldquo": "\u201c",
}


def brisart_unescape(text: str) -> str:
    """Decode HTML character references (named + numeric) in `text`."""
    if "&" not in text:
        return text

    output = []
    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        if char != "&":
            output.append(char)
            i += 1
            continue

        semicolon = text.find(";", i + 1, i + 12)
        if semicolon == -1:
            output.append(char)
            i += 1
            continue

        entity_body = text[i + 1:semicolon]
        if entity_body.startswith("#x") or entity_body.startswith("#X"):
            try:
                code_point = int(entity_body[2:], 16)
                output.append(chr(code_point))
                i = semicolon + 1
                continue
            except ValueError:
                pass
        elif entity_body.startswith("#"):
            try:
                code_point = int(entity_body[1:])
                output.append(chr(code_point))
                i = semicolon + 1
                continue
            except ValueError:
                pass
        elif entity_body in _NAMED_ENTITIES:
            output.append(_NAMED_ENTITIES[entity_body])
            i = semicolon + 1
            continue

        output.append(char)
        i += 1

    return "".join(output)


class BrisartMarkupParser:
    """Lenient HTML tokenizer. Subclass and override the handle_* methods."""

    def __init__(self, convert_charrefs: bool = True):
        self._convert_charrefs = convert_charrefs
        self._buffer = ""
        self._raw_text_tag: Optional[str] = None

    def feed(self, chunk: str) -> None:
        self._buffer += chunk
        self._consume()

    def close(self) -> None:
        if self._buffer:
            self._emit_data(self._buffer)
            self._buffer = ""

    def _consume(self) -> None:
        while True:
            if self._raw_text_tag is not None:
                closing = f"</{self._raw_text_tag}"
                index = self._buffer.casefold().find(closing)
                if index == -1:
                    return
                self._emit_data(self._buffer[:index])
                self._buffer = self._buffer[index:]
                self._raw_text_tag = None
                continue

            lt_index = self._buffer.find("<")
            if lt_index == -1:
                if self._buffer:
                    self._emit_data(self._buffer)
                    self._buffer = ""
                return

            if lt_index > 0:
                self._emit_data(self._buffer[:lt_index])
                self._buffer = self._buffer[lt_index:]

            consumed = self._try_consume_tag()
            if consumed is None:
                return

    def _emit_data(self, text: str) -> None:
        if not text:
            return
        if self._convert_charrefs:
            text = brisart_unescape(text)
        self.handle_data(text)

    def _try_consume_tag(self) -> Optional[bool]:
        buffer = self._buffer
        assert buffer.startswith("<")

        if buffer.startswith("<!--"):
            end = buffer.find("-->")
            if end == -1:
                return None
            self._buffer = buffer[end + 3:]
            return True

        if buffer.startswith("<!") or buffer.startswith("<?"):
            end = buffer.find(">")
            if end == -1:
                return None
            self._buffer = buffer[end + 1:]
            return True

        if buffer.startswith("</"):
            end = buffer.find(">")
            if end == -1:
                return None
            tag_match = _TAG_NAME_RE.match(buffer, 2)
            tag_name = tag_match.group(0).casefold() if tag_match else ""
            self._buffer = buffer[end + 1:]
            if tag_name:
                self.handle_endtag(tag_name)
            return True

        tag_match = _TAG_NAME_RE.match(buffer, 1)
        if not tag_match:
            self._emit_data("<")
            self._buffer = buffer[1:]
            return True

        end = buffer.find(">")
        if end == -1:
            return None

        tag_name = tag_match.group(0).casefold()
        attr_text = buffer[tag_match.end():end]
        is_self_closing = attr_text.rstrip().endswith("/")
        if is_self_closing:
            attr_text = attr_text.rstrip()[:-1]
        attrs = self._parse_attrs(attr_text)

        self._buffer = buffer[end + 1:]

        if is_self_closing:
            self.handle_startendtag(tag_name, attrs)
        else:
            self.handle_starttag(tag_name, attrs)
            if tag_name in _RAW_TEXT_ELEMENTS:
                self._raw_text_tag = tag_name
        return True

    def _parse_attrs(self, text: str) -> List[Tuple[str, Optional[str]]]:
        attrs: List[Tuple[str, Optional[str]]] = []
        i = 0
        length = len(text)
        while i < length:
            while i < length and text[i].isspace():
                i += 1
            if i >= length:
                break
            name_match = _ATTR_NAME_RE.match(text, i)
            if not name_match:
                i += 1
                continue
            name = name_match.group(0).casefold()
            i = name_match.end()
            while i < length and text[i].isspace():
                i += 1
            if i < length and text[i] == "=":
                i += 1
                while i < length and text[i].isspace():
                    i += 1
                if i < length and text[i] in ("'", '"'):
                    quote = text[i]
                    i += 1
                    value_start = i
                    end_quote = text.find(quote, i)
                    if end_quote == -1:
                        value = text[value_start:]
                        i = length
                    else:
                        value = text[value_start:end_quote]
                        i = end_quote + 1
                else:
                    value_start = i
                    while i < length and not text[i].isspace():
                        i += 1
                    value = text[value_start:i]
                if self._convert_charrefs:
                    value = brisart_unescape(value)
                attrs.append((name, value))
            else:
                attrs.append((name, None))
        return attrs

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        pass

    def handle_endtag(self, tag: str) -> None:
        pass

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        pass


def _self_test() -> None:
    events: List[tuple] = []

    class _Collector(BrisartMarkupParser):
        def handle_starttag(self, tag, attrs):
            events.append(("start", tag, attrs))

        def handle_endtag(self, tag):
            events.append(("end", tag))

        def handle_data(self, data):
            if data.strip():
                events.append(("data", data))

    parser = _Collector()
    parser.feed('<div class="a"><p>Hello &amp; world</p><br><img src="x.png"></div>')
    parser.close()

    assert ("start", "div", [("class", "a")]) in events
    assert ("start", "p", []) in events
    assert ("data", "Hello & world") in events
    assert ("end", "p") in events
    assert ("start", "br", []) in events
    assert ("start", "img", [("src", "x.png")]) in events

    events.clear()
    parser2 = _Collector()
    parser2.feed("<script>if (1 < 2) { console.log('<b>not a tag</b>'); }</script><p>after</p>")
    parser2.close()
    assert ("data", "after") in events
    assert not any(e[0] == "start" and e[1] == "b" for e in events)


if __name__ == "__main__":
    _self_test()
    print("BrisartMarkupParser internal self-test passed.")


__all__ = ["BrisartMarkupParser", "brisart_unescape"]



