"""Tests for brisart_ai/native/brisart_url.py -- BrisartURL vs. real urllib.parse."""
import urllib.parse
import unittest
from brisart_ai.native.brisart_url import (
    brisart_parse_qsl, brisart_quote, brisart_unquote, brisart_urlencode,
    brisart_urljoin, brisart_urlsplit, brisart_urlunsplit,
)


class TestBrisartUrlsplit(unittest.TestCase):
    def test_full_url_matches_stdlib(self):
        url = "https://Example.COM:8080/a/b?x=1&y=2#frag"
        ours = brisart_urlsplit(url)
        theirs = urllib.parse.urlsplit(url)
        self.assertEqual(ours.scheme, theirs.scheme)
        self.assertEqual(ours.netloc, theirs.netloc)
        self.assertEqual(ours.path, theirs.path)
        self.assertEqual(ours.query, theirs.query)
        self.assertEqual(ours.fragment, theirs.fragment)

    def test_hostname_lowercased_and_port_stripped(self):
        self.assertEqual(brisart_urlsplit("https://Example.COM:8080/x").hostname, "example.com")

    def test_ipv6_hostname(self):
        self.assertEqual(brisart_urlsplit("http://[::1]:8080/x").hostname, "::1")

    def test_schemeless_url_has_empty_scheme(self):
        self.assertEqual(brisart_urlsplit("example.com/x").scheme, "")

    def test_urlunsplit_round_trip(self):
        url = "https://example.com/a/b?x=1#frag"
        self.assertEqual(brisart_urlunsplit(brisart_urlsplit(url)), url)


class TestBrisartQuoteUnquote(unittest.TestCase):
    def test_quote_matches_stdlib_default_safe(self):
        text = "a b/c?d=e"
        self.assertEqual(brisart_quote(text, safe="/"), urllib.parse.quote(text, safe="/"))

    def test_unquote_matches_stdlib(self):
        text = "a%20b/c%3Fd%3De"
        self.assertEqual(brisart_unquote(text), urllib.parse.unquote(text))

    def test_malformed_percent_escape_left_untouched(self):
        self.assertEqual(brisart_unquote("100%"), "100%")

    def test_round_trip(self):
        original = "hello world/with spaces & symbols!"
        self.assertEqual(brisart_unquote(brisart_quote(original, safe="")), original)


class TestBrisartUrljoin(unittest.TestCase):
    def test_relative_path_matches_stdlib(self):
        cases = [
            ("https://a.com/x/y", "z"),
            ("https://a.com/x/y", "/z"),
            ("https://a.com/x/y/", "../z"),
            ("https://a.com/x", "//other.com/y"),
            ("https://a.com/x/y", "?q=1"),
            ("https://a.com/x/y#old", "#new"),
        ]
        for base, ref in cases:
            self.assertEqual(brisart_urljoin(base, ref), urllib.parse.urljoin(base, ref), msg=f"{base} + {ref}")

    def test_dot_segment_removal(self):
        self.assertEqual(brisart_urljoin("https://a.com/x/y/", "../z"), "https://a.com/x/z")


class TestBrisartQueryEncoding(unittest.TestCase):
    def test_urlencode_matches_stdlib_for_spaces(self):
        pairs = [("q", "hello world"), ("a", "b c")]
        self.assertEqual(brisart_urlencode(pairs), urllib.parse.urlencode(pairs))

    def test_parse_qsl_matches_stdlib(self):
        query = "a=1&b=hello+world&c="
        self.assertEqual(
            brisart_parse_qsl(query, keep_blank_values=True),
            urllib.parse.parse_qsl(query, keep_blank_values=True),
        )

    def test_parse_qsl_drops_blank_by_default(self):
        self.assertEqual(brisart_parse_qsl("a=1&b="), [("a", "1")])


if __name__ == "__main__":
    unittest.main()
