"""
File: brisart_ai/native/tests/test_brisart_robots.py

Purpose
-------
Unit tests for brisart_ai.native.brisart_robots. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 10 test cases across TestBrisartRobotsPolicy.

Communication / relationships
------------------------------
- exercises brisart_ai.native.brisart_robots (BrisartRobotsPolicy)

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
- asserts: first match in file order wins not most specific.
- asserts: empty disallow means allow everything.
- asserts: no policy at all allows everything.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/native/tests/test_brisart_robots.py -v
    $ python -m pytest brisart_ai/native/tests/test_brisart_robots.py --import-mode=importlib
"""
import unittest
from brisart_ai.native.brisart_robots import BrisartRobotsPolicy


class TestBrisartRobotsPolicy(unittest.TestCase):
    def test_simple_disallow(self):
        policy = BrisartRobotsPolicy()
        policy.parse("User-agent: *\nDisallow: /private/\n".splitlines())
        self.assertFalse(policy.can_fetch("Bot/1.0", "https://example.com/private/x"))
        self.assertTrue(policy.can_fetch("Bot/1.0", "https://example.com/public/x"))

    def test_first_match_in_file_order_wins_not_most_specific(self):
        # Mirrors urllib.robotparser's actual (non-RFC-9309) algorithm:
        # first matching rule in file order wins, not "most specific path".
        sample = (
            "User-agent: *\n"
            "Disallow: /private/\n"
            "Allow: /private/public-page.html\n"
        ).splitlines()
        policy = BrisartRobotsPolicy()
        policy.parse(sample)
        # Disallow comes first and already matches the prefix -> wins outright.
        self.assertFalse(policy.can_fetch("Bot/1.0", "https://example.com/private/public-page.html"))

    def test_empty_disallow_means_allow_everything(self):
        policy = BrisartRobotsPolicy()
        policy.parse("User-agent: *\nDisallow:\n".splitlines())
        self.assertTrue(policy.can_fetch("Bot/1.0", "https://example.com/anything"))

    def test_no_policy_at_all_allows_everything(self):
        policy = BrisartRobotsPolicy()
        policy.parse([])
        self.assertTrue(policy.can_fetch("Bot/1.0", "https://example.com/anything"))

    def test_ruleless_group_before_blank_line_is_discarded(self):
        discarded = (
            "User-agent: GhostBot\n"
            "\n"
            "User-agent: *\n"
            "Disallow: /blocked/\n"
        ).splitlines()
        policy = BrisartRobotsPolicy()
        policy.parse(discarded)
        # GhostBot's own (ruleless) group was discarded, so it falls
        # through to the default "*" group instead.
        self.assertFalse(policy.can_fetch("GhostBot/1.0", "https://example.com/blocked/x"))

    def test_group_mixing_wildcard_with_named_agent_is_default_only(self):
        mixed = (
            "User-agent: googlebot\n"
            "User-agent: *\n"
            "Disallow: /mixed-block/\n"
        ).splitlines()
        policy = BrisartRobotsPolicy()
        policy.parse(mixed)
        self.assertFalse(policy.can_fetch("googlebot/2.1", "https://example.com/mixed-block/x"))

    def test_named_agent_group_takes_priority_over_default(self):
        sample = (
            "User-agent: *\n"
            "Disallow: /\n"
            "\n"
            "User-agent: GoodBot\n"
            "Allow: /\n"
        ).splitlines()
        policy = BrisartRobotsPolicy()
        policy.parse(sample)
        self.assertTrue(policy.can_fetch("GoodBot/1.0", "https://example.com/anything"))
        self.assertFalse(policy.can_fetch("OtherBot/1.0", "https://example.com/anything"))

    def test_crawl_delay_parsed_when_numeric(self):
        policy = BrisartRobotsPolicy()
        policy.parse("User-agent: *\nCrawl-delay: 2\n".splitlines())
        self.assertEqual(policy.crawl_delay("Bot/1.0"), 2.0)

    def test_crawl_delay_ignored_when_non_numeric(self):
        policy = BrisartRobotsPolicy()
        policy.parse("User-agent: *\nCrawl-delay: soon\n".splitlines())
        self.assertIsNone(policy.crawl_delay("Bot/1.0"))

    def test_can_fetch_handles_query_string_in_path(self):
        policy = BrisartRobotsPolicy()
        policy.parse("User-agent: *\nDisallow: /search\n".splitlines())
        self.assertFalse(policy.can_fetch("Bot/1.0", "https://example.com/search?q=x"))


if __name__ == "__main__":
    unittest.main()



