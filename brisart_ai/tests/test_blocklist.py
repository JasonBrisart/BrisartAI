"""Tests for brisart_ai/blocklist.py -- shared web source-blocking policy."""
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
