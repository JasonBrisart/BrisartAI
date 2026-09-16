"""
File: brisart_ai/knowledge/tests/test_authority.py

Purpose
-------
Unit tests for brisart_ai.knowledge.authority. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 11 test cases across TestClassifyAuthorityTier, TestAuthorityMultiplier.

Communication / relationships
------------------------------
- exercises brisart_ai.knowledge.authority (MULTIPLIER_CEILING, MULTIPLIER_FLOOR, TIER_ENCYCLOPEDIC, TIER_ESTABLISHED_NEWS, TIER_GOVERNMENTAL_ACADEMIC, TIER_LOW_VALUE)

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
- asserts: empty location.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/knowledge/tests/test_authority.py -v
    $ python -m pytest brisart_ai/knowledge/tests/test_authority.py --import-mode=importlib
"""
import unittest

from brisart_ai.knowledge.authority import (
    MULTIPLIER_CEILING, MULTIPLIER_FLOOR, TIER_ENCYCLOPEDIC,
    TIER_ESTABLISHED_NEWS, TIER_GOVERNMENTAL_ACADEMIC, TIER_LOW_VALUE,
    TIER_NEUTRAL, authority_multiplier, classify_authority_tier,
)


class TestClassifyAuthorityTier(unittest.TestCase):
    def test_empty_location(self):
        self.assertEqual(classify_authority_tier(""), TIER_NEUTRAL)

    def test_local_file_path(self):
        self.assertEqual(classify_authority_tier("/local/file.txt"), TIER_NEUTRAL)

    def test_wikipedia_is_encyclopedic(self):
        self.assertEqual(classify_authority_tier("https://en.wikipedia.org/wiki/Cat"), TIER_ENCYCLOPEDIC)

    def test_gov_tld_is_governmental(self):
        self.assertEqual(classify_authority_tier("https://www.nist.gov/x"), TIER_GOVERNMENTAL_ACADEMIC)

    def test_edu_tld_is_governmental_academic(self):
        self.assertEqual(classify_authority_tier("https://mit.edu/x"), TIER_GOVERNMENTAL_ACADEMIC)

    def test_reuters_is_established_news(self):
        self.assertEqual(classify_authority_tier("https://www.reuters.com/x"), TIER_ESTABLISHED_NEWS)

    def test_reddit_is_low_value(self):
        self.assertEqual(classify_authority_tier("https://www.reddit.com/r/x"), TIER_LOW_VALUE)

    def test_ordinary_host_is_neutral(self):
        self.assertEqual(classify_authority_tier("https://example.com/x"), TIER_NEUTRAL)

    def test_false_match_guarded_against(self):
        self.assertEqual(
            classify_authority_tier("https://not-wikipedia.org.evil-site.com/x"), TIER_NEUTRAL,
        )


class TestAuthorityMultiplier(unittest.TestCase):
    def test_bounded_within_floor_and_ceiling(self):
        for location in [
            "https://en.wikipedia.org/wiki/Cat", "https://www.reddit.com/x",
            "https://mit.edu/x", "https://example.com/x", "",
        ]:
            multiplier = authority_multiplier(location)
            self.assertGreaterEqual(multiplier, MULTIPLIER_FLOOR)
            self.assertLessEqual(multiplier, MULTIPLIER_CEILING)

    def test_neutral_default_is_one(self):
        self.assertEqual(authority_multiplier(""), 1.0)
        self.assertEqual(authority_multiplier("https://example.com/x"), 1.0)


if __name__ == "__main__":
    unittest.main()



