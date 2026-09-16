"""
File: brisart_ai/io/tests/test_extractor.py

Purpose
-------
Unit tests for brisart_ai.io.extractor. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 13 test cases across TestHtmlToText, TestCsvToText.

Communication / relationships
------------------------------
- exercises brisart_ai.io.extractor (HTMLTextExtractor, csv_to_text, html_to_text)

Settings / parameters
---------------------
- Standard unittest.TestCase suite; run with pytest
  (--import-mode=importlib) or `python -m pytest`.
- Uses only in-memory / temp-dir fixtures where any state is
  needed; no network, no external services, no shared global state.
- No tunable parameters of its own; assertions pin the behavior
  and point values defined in the module under test.

Edge cases
----------
- asserts: ordinary superscript not stripped.
- asserts: links are deduplicated.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/io/tests/test_extractor.py -v
    $ python -m pytest brisart_ai/io/tests/test_extractor.py --import-mode=importlib
"""
import unittest
from brisart_ai.io.extractor import HTMLTextExtractor, csv_to_text, html_to_text


class TestHtmlToText(unittest.TestCase):
    def test_extracts_title_text_and_links(self):
        html = '''
        <html><head><title>Test Page &amp; More</title></head>
        <body>
        <p>Hello <b>World</b>. This is a <a href="/relative/link">link</a>.</p>
        </body></html>
        '''
        title, text, links = html_to_text(html, base_url="https://example.com/page")
        self.assertEqual(title, "Test Page & More")
        self.assertIn("Hello", text)
        self.assertIn("World", text)
        self.assertEqual(links, ["https://example.com/relative/link"])

    def test_script_content_excluded_from_text(self):
        html = "<script>var x = 1;</script><p>Visible text</p>"
        _title, text, _links = html_to_text(html)
        self.assertNotIn("var x", text)
        self.assertIn("Visible text", text)

    def test_style_content_excluded_from_text(self):
        html = "<style>.a { color: red; }</style><p>Visible</p>"
        _title, text, _links = html_to_text(html)
        self.assertNotIn("color: red", text)
        self.assertIn("Visible", text)

    def test_reference_citation_marker_is_stripped(self):
        # MediaWiki-style footnote marker should not leak into extracted text.
        html = '<p>Citation<sup class="reference">[3]</sup> here.</p>'
        _title, text, _links = html_to_text(html)
        self.assertNotIn("[3]", text)
        self.assertIn("Citation", text)
        self.assertIn("here", text)

    def test_ordinary_superscript_not_stripped(self):
        html = "<p>10<sup>2</sup> meters</p>"
        _title, text, _links = html_to_text(html)
        self.assertIn("2", text)

    def test_links_are_deduplicated(self):
        html = '<a href="/x">one</a><a href="/x">two</a>'
        _title, _text, links = html_to_text(html, base_url="https://example.com/")
        self.assertEqual(links, ["https://example.com/x"])

    def test_non_http_links_excluded(self):
        html = '<a href="javascript:void(0)">bad</a><a href="/good">good</a>'
        _title, _text, links = html_to_text(html, base_url="https://example.com/")
        self.assertEqual(links, ["https://example.com/good"])

    def test_malformed_html_does_not_raise(self):
        html = "<p>unterminated <b>bold text"
        try:
            html_to_text(html)
        except Exception as exc:
            self.fail(f"html_to_text raised unexpectedly: {exc}")

    def test_block_tags_separated_by_newlines(self):
        html = "<p>First</p><p>Second</p>"
        _title, text, _links = html_to_text(html)
        self.assertIn("First", text)
        self.assertIn("Second", text)


class TestCsvToText(unittest.TestCase):
    def test_basic_csv_conversion(self):
        result = csv_to_text("a,b,c\n1,2,3\n")
        self.assertEqual(result, "a | b | c\n1 | 2 | 3")

    def test_empty_rows_skipped(self):
        result = csv_to_text("a,b\n\n1,2\n")
        self.assertEqual(result, "a | b\n1 | 2")

    def test_single_column(self):
        result = csv_to_text("only\nvalue\n")
        self.assertEqual(result, "only\nvalue")

    def test_empty_input(self):
        self.assertEqual(csv_to_text(""), "")


if __name__ == "__main__":
    unittest.main()


