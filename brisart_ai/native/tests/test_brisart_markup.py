"""Tests for brisart_ai/native/brisart_markup.py -- BrisartMarkupParser HTML tokenizer."""
import unittest
from brisart_ai.native.brisart_markup import BrisartMarkupParser, brisart_unescape


class _Collector(BrisartMarkupParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events = []

    def handle_starttag(self, tag, attrs):
        self.events.append(("start", tag, attrs))

    def handle_endtag(self, tag):
        self.events.append(("end", tag))

    def handle_data(self, data):
        if data.strip():
            self.events.append(("data", data))


class TestBrisartUnescape(unittest.TestCase):
    def test_named_entities(self):
        self.assertEqual(brisart_unescape("Tom &amp; Jerry"), "Tom & Jerry")
        self.assertEqual(brisart_unescape("&lt;tag&gt;"), "<tag>")

    def test_numeric_decimal_entity(self):
        self.assertEqual(brisart_unescape("&#233;"), "\u00e9")

    def test_numeric_hex_entity(self):
        self.assertEqual(brisart_unescape("&#x00e9;"), "\u00e9")

    def test_text_without_ampersand_is_unchanged(self):
        self.assertEqual(brisart_unescape("plain text"), "plain text")


class TestBrisartMarkupParser(unittest.TestCase):
    def test_basic_tag_and_data_events(self):
        p = _Collector()
        p.feed('<div class="a"><p>Hello &amp; world</p></div>')
        p.close()
        self.assertIn(("start", "div", [("class", "a")]), p.events)
        self.assertIn(("start", "p", []), p.events)
        self.assertIn(("data", "Hello & world"), p.events)
        self.assertIn(("end", "p"), p.events)

    def test_bare_void_element_fires_starttag_not_startendtag(self):
        # A bare <br> (no explicit slash) must fire handle_starttag(), matching
        # html.parser.HTMLParser -- not handle_startendtag() -- since the
        # source markup itself carries no trailing "/".
        p = _Collector()
        p.feed("<br>")
        p.close()
        self.assertIn(("start", "br", []), p.events)

    def test_explicit_self_closing_tag_fires_both(self):
        p = _Collector()
        p.feed('<img src="x.png"/>')
        p.close()
        self.assertIn(("start", "img", [("src", "x.png")]), p.events)
        self.assertIn(("end", "img"), p.events)

    def test_script_content_is_not_tokenized(self):
        p = _Collector()
        p.feed("<script>if (1 < 2) { console.log('<b>not a tag</b>'); }</script><p>after</p>")
        p.close()
        self.assertIn(("data", "after"), p.events)
        self.assertFalse(any(e[0] == "start" and e[1] == "b" for e in p.events))

    def test_comment_is_skipped(self):
        p = _Collector()
        p.feed("<!-- a comment --><p>real</p>")
        p.close()
        self.assertIn(("data", "real"), p.events)

    def test_incremental_feed_across_boundary(self):
        # Plain text data is emitted as soon as it's seen (not buffered
        # across feed() calls); only an in-progress TAG or entity
        # reference is buffered until it can be completed. Concatenating
        # every data event should still reconstruct the full text.
        p = _Collector()
        p.feed("<p>Hel")
        p.feed("lo</p>")
        p.close()
        reconstructed = "".join(e[1] for e in p.events if e[0] == "data")
        self.assertEqual(reconstructed, "Hello")

    def test_partial_tag_across_feed_boundary_is_buffered(self):
        # An in-progress tag split across feed() calls must NOT be
        # emitted as literal data -- it should be buffered until the
        # closing '>' arrives on the next feed() call.
        p = _Collector()
        p.feed("<p cla")
        p.feed('ss="x">hi</p>')
        p.close()
        self.assertIn(("start", "p", [("class", "x")]), p.events)
        self.assertIn(("data", "hi"), p.events)

    def test_malformed_lone_lt_treated_as_literal(self):
        p = _Collector()
        p.feed("a < b")
        p.close()
        # Should not raise; some data event should be produced.
        self.assertTrue(any(e[0] == "data" for e in p.events))

    def test_quoted_attribute_values(self):
        p = _Collector()
        p.feed("<a href='single' title=\"double\">link</a>")
        p.close()
        starts = [e for e in p.events if e[0] == "start" and e[1] == "a"]
        self.assertEqual(len(starts), 1)
        attrs = dict(starts[0][2])
        self.assertEqual(attrs.get("href"), "single")
        self.assertEqual(attrs.get("title"), "double")


if __name__ == "__main__":
    unittest.main()
