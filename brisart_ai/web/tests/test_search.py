"""
File: brisart_ai/web/tests/test_search.py

Purpose
-------
Unit tests for brisart_ai.web.search. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 24 test cases across TestDecodeDuckDuckGoTarget, TestDecodeBingTarget, TestRemoveTrackingParameters, TestIsSearchHost, TestNormalizeResultUrl, TestDeduplicate, TestPartitionRelatedResults.

Communication / relationships
------------------------------
- exercises brisart_ai.web.search (_decode_bing_target, _decode_duckduckgo_target, _deduplicate, _is_search_host, _normalize_result_url, _partition_related_results)
- exercises brisart_ai.native.brisart_codec (brisart_urlsafe_b64decode, brisart_b64encode)

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
- asserts: missing uddg parameter returns original.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/web/tests/test_search.py -v
    $ python -m pytest brisart_ai/web/tests/test_search.py --import-mode=importlib
"""
import unittest
from brisart_ai.web.search import (
    _decode_bing_target, _decode_duckduckgo_target, _deduplicate, _is_search_host,
    _normalize_result_url, _partition_related_results, _remove_tracking_parameters,
)
from brisart_ai.native.brisart_codec import brisart_urlsafe_b64decode, brisart_b64encode


class TestDecodeDuckDuckGoTarget(unittest.TestCase):
    def test_unwraps_uddg_redirect(self):
        wrapped = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage&rut=abc"
        self.assertEqual(_decode_duckduckgo_target(wrapped), "https://example.com/page")

    def test_non_duckduckgo_url_returned_unchanged(self):
        url = "https://example.com/x"
        self.assertEqual(_decode_duckduckgo_target(url), url)

    def test_missing_uddg_parameter_returns_original(self):
        url = "https://duckduckgo.com/l/?rut=abc"
        self.assertEqual(_decode_duckduckgo_target(url), url)


class TestDecodeBingTarget(unittest.TestCase):
    def test_unwraps_ck_a_redirect(self):
        real_url = b"https://example.com/real-page"
        encoded = brisart_b64encode(real_url, urlsafe=True).rstrip(b"=").decode("ascii")
        wrapped = f"https://www.bing.com/ck/a?!&&p=abc&u=a1{encoded}&ntb=1"
        self.assertEqual(_decode_bing_target(wrapped), "https://example.com/real-page")

    def test_non_bing_url_returned_unchanged(self):
        url = "https://example.com/x"
        self.assertEqual(_decode_bing_target(url), url)

    def test_bing_url_without_ck_a_path_returned_unchanged(self):
        url = "https://www.bing.com/search?q=x"
        self.assertEqual(_decode_bing_target(url), url)


class TestRemoveTrackingParameters(unittest.TestCase):
    def test_utm_parameters_stripped(self):
        url = "https://example.com/x?utm_source=a&utm_campaign=b&real=keep"
        result = _remove_tracking_parameters(url)
        self.assertNotIn("utm_source", result)
        self.assertNotIn("utm_campaign", result)
        self.assertIn("real=keep", result)

    def test_fbclid_stripped(self):
        url = "https://example.com/x?fbclid=abc123&keep=1"
        result = _remove_tracking_parameters(url)
        self.assertNotIn("fbclid", result)
        self.assertIn("keep=1", result)

    def test_no_tracking_params_unchanged_semantically(self):
        url = "https://example.com/x?a=1&b=2"
        result = _remove_tracking_parameters(url)
        self.assertIn("a=1", result)
        self.assertIn("b=2", result)


class TestIsSearchHost(unittest.TestCase):
    def test_bing_is_search_host(self):
        self.assertTrue(_is_search_host("www.bing.com"))

    def test_duckduckgo_is_search_host(self):
        self.assertTrue(_is_search_host("html.duckduckgo.com"))

    def test_ordinary_host_is_not_search_host(self):
        self.assertFalse(_is_search_host("example.com"))


class TestNormalizeResultUrl(unittest.TestCase):
    def test_relative_url_resolved_against_base(self):
        result = _normalize_result_url("/page", "https://example.com/dir/")
        self.assertEqual(result, "https://example.com/page")

    def test_javascript_scheme_rejected(self):
        self.assertEqual(_normalize_result_url("javascript:void(0)", "https://example.com/"), "")

    def test_search_engine_host_rejected(self):
        result = _normalize_result_url("https://www.bing.com/search?q=x", "https://www.bing.com/")
        self.assertEqual(result, "")

    def test_blocked_dictionary_host_rejected(self):
        result = _normalize_result_url("https://www.merriam-webster.com/dictionary/x", "https://example.com/")
        self.assertEqual(result, "")

    def test_genuine_external_link_accepted(self):
        result = _normalize_result_url("https://en.wikipedia.org/wiki/Cat", "https://www.bing.com/")
        self.assertEqual(result, "https://en.wikipedia.org/wiki/Cat")


class TestDeduplicate(unittest.TestCase):
    def test_removes_exact_duplicate_urls(self):
        results = [("https://a.com/x", "A"), ("https://a.com/x", "A dup")]
        deduped = _deduplicate(results, limit=10)
        self.assertEqual(len(deduped), 1)

    def test_trailing_slash_treated_as_duplicate(self):
        results = [("https://a.com/x", "A"), ("https://a.com/x/", "A2")]
        deduped = _deduplicate(results, limit=10)
        self.assertEqual(len(deduped), 1)

    def test_respects_limit(self):
        results = [(f"https://a.com/{i}", f"T{i}") for i in range(10)]
        deduped = _deduplicate(results, limit=3)
        self.assertEqual(len(deduped), 3)


class TestPartitionRelatedResults(unittest.TestCase):
    def test_related_result_kept(self):
        results = [("https://example.com/microsoft-history", "History of Microsoft")]
        related, unrelated = _partition_related_results("who founded microsoft", results)
        self.assertEqual(len(related), 1)
        self.assertEqual(len(unrelated), 0)

    def test_unrelated_result_partitioned_out(self):
        results = [("https://example.com/unrelated-topic", "Completely Different Subject")]
        related, unrelated = _partition_related_results("who founded microsoft", results)
        self.assertEqual(len(related), 0)
        self.assertEqual(len(unrelated), 1)

    def test_mixed_batch_partitioned_individually(self):
        # This is the actual fix for the "Tesla vandalism" decoy-result bug:
        # a single unrelated result must not be waved through just because
        # other results in the same batch are on-topic.
        results = [
            ("https://example.com/microsoft-history", "History of Microsoft"),
            ("https://example.com/unrelated-vandalism", "2025 Article Vandalism Incident"),
        ]
        related, unrelated = _partition_related_results("who founded microsoft", results)
        self.assertEqual(len(related), 1)
        self.assertEqual(len(unrelated), 1)

    def test_no_meaningful_terms_returns_all_as_related(self):
        results = [("https://example.com/x", "Something")]
        related, unrelated = _partition_related_results("a an the", results)
        self.assertEqual(len(related), 1)
        self.assertEqual(len(unrelated), 0)

    def test_three_letter_subject_words_are_meaningful(self):
        # Regression: a query whose only meaningful words are 3 letters
        # ("won", "war", "ceo", "tax") must NOT collapse to an empty term
        # set that waves every unrelated decoy through as "related".
        garbage = [
            ("https://example.com/cats", "The Cutest Cats of Instagram"),
            ("https://shop.example.com/sale", "Huge Summer Sale"),
            ("https://example.com/weather", "Local Weather Forecast"),
        ]
        for query in ("who won the war", "who is the ceo", "what is the tax"):
            related, unrelated = _partition_related_results(query, garbage)
            self.assertEqual(related, [], msg=f"{query!r} should drop all decoys")
            self.assertEqual(len(unrelated), len(garbage))

    def test_substring_false_positives_are_dropped(self):
        # A short topic word must NOT relate a result just because it appears
        # as a SUBSTRING of an unrelated word: "war" in "warehouse", "tax" in
        # "taxi", "won" in "wonderland", "end" in "friend". Matching is on
        # whole-word boundaries, not raw substrings.
        cases = [
            ("who won the war", ("https://x.com/a", "Amazon Warehouse Jobs")),
            ("what is the tax rate", ("https://x.com/b", "Book a Taxi Online")),
            ("who won the game", ("https://x.com/c", "Wonderland Theme Park")),
            ("what year did it end", ("https://x.com/d", "Best Friend Gift Ideas")),
        ]
        for query, result in cases:
            related, unrelated = _partition_related_results(query, [result])
            self.assertEqual(related, [], msg=f"{query!r} must not match {result[1]!r} on a substring")
            self.assertEqual(len(unrelated), 1)

    def test_plural_fold_still_matches_whole_words(self):
        # Word-boundary matching must still fold a single trailing 's' so a
        # plural query term matches a singular document word and vice versa.
        related, _ = _partition_related_results(
            "how many cats are in america",
            [("https://example.com/cat-population", "Pet Cat Population Statistics")],
        )
        self.assertEqual(len(related), 1)
        related2, _ = _partition_related_results(
            "history of the cat",
            [("https://example.com/cats", "All About Cats")],
        )
        self.assertEqual(len(related2), 1)

    def test_decoy_sharing_no_topic_word_is_dropped(self):
        # "who won the 2020 election" must keep election results and drop a
        # page that shares none of {won, 2020, election}.
        batch = [
            ("https://en.wikipedia.org/wiki/2020_United_States_presidential_election",
             "2020 United States presidential election"),
            ("https://example.com/cats", "The Cutest Cats of Instagram"),
        ]
        related, unrelated = _partition_related_results("who won the 2020 election", batch)
        self.assertEqual([t for _, t in unrelated], ["The Cutest Cats of Instagram"])
        self.assertEqual(len(related), 1)


if __name__ == "__main__":
    unittest.main()




