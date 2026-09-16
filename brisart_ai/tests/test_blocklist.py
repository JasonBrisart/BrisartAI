"""
File: brisart_ai/tests/test_blocklist.py

Purpose
-------
Unit tests for brisart_ai.blocklist. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 13 test cases across TestIsBlockedWebHost, TestIsOfftopicWiki, TestIsJunkWebSource.

Communication / relationships
------------------------------
- exercises brisart_ai.blocklist (BLOCKED_WEB_HOSTS, is_blocked_web_host, is_junk_web_source, is_offtopic_wiki)

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
- asserts: empty location returns false.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/tests/test_blocklist.py -v
    $ python -m pytest brisart_ai/tests/test_blocklist.py --import-mode=importlib
"""
import unittest
from brisart_ai.blocklist import (
    BLOCKED_WEB_HOSTS, is_blocked_web_host, is_junk_web_source, is_offtopic_wiki,
)


class TestIsBlockedWebHost(unittest.TestCase):
    def test_blocked_dictionary_host(self):
        self.assertTrue(is_blocked_web_host("https://www.merriam-webster.com/dictionary/many"))

    def test_blocked_host_subdomain(self):
        self.assertTrue(is_blocked_web_host("https://sub.merriam-webster.com/x"))

    def test_non_blocked_host(self):
        self.assertFalse(is_blocked_web_host("https://en.wikipedia.org/wiki/Cat"))

    def test_bare_hostname_without_scheme_returns_false(self):
        # Requires an absolute URL with a scheme -- documented constraint.
        self.assertFalse(is_blocked_web_host("merriam-webster.com"))

    def test_empty_location_returns_false(self):
        self.assertFalse(is_blocked_web_host(""))

    def test_all_blocked_hosts_are_actually_blocked(self):
        for host in BLOCKED_WEB_HOSTS:
            self.assertTrue(is_blocked_web_host(f"https://{host}/x"), msg=f"{host} should be blocked")


class TestIsOfftopicWiki(unittest.TestCase):
    def test_bare_function_word_wiki_page_is_offtopic(self):
        self.assertTrue(is_offtopic_wiki("https://en.wikipedia.org/wiki/Many"))

    def test_genuine_topic_wiki_page_is_not_offtopic(self):
        self.assertFalse(is_offtopic_wiki("https://en.wikipedia.org/wiki/Cat"))

    def test_non_wikipedia_host_returns_false(self):
        self.assertFalse(is_offtopic_wiki("https://example.com/wiki/Many"))

    def test_topic_terms_override_exemption(self):
        # If "many" is actually part of the topic being searched for, don't reject it.
        self.assertFalse(is_offtopic_wiki("https://en.wikipedia.org/wiki/Many", topic_terms={"many"}))


class TestIsJunkWebSource(unittest.TestCase):
    def test_blocked_host_is_junk(self):
        self.assertTrue(is_junk_web_source("https://thefreedictionary.com/x"))

    def test_offtopic_wiki_is_junk(self):
        self.assertTrue(is_junk_web_source("https://en.wikipedia.org/wiki/Many"))

    def test_genuine_source_is_not_junk(self):
        self.assertFalse(is_junk_web_source("https://en.wikipedia.org/wiki/Microsoft"))


if __name__ == "__main__":
    unittest.main()


