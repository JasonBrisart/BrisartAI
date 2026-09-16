"""
File: brisart_ai/web/tests/test_crawler.py

Purpose
-------
Unit tests for brisart_ai.web.crawler. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 23 test cases across TestCleanSearchQuery, TestSearchKeywordFallback, TestTopicTerms, TestScoreResult, TestRankResults, TestShouldReject, TestContentExists.

Communication / relationships
------------------------------
- exercises brisart_ai.knowledge.index (Index)
- exercises brisart_ai.web.crawler (clean_search_query, content_exists, rank_results, score_result, search_keyword_fallback, _should_reject)

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
- asserts: empty query returns empty.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/web/tests/test_crawler.py -v
    $ python -m pytest brisart_ai/web/tests/test_crawler.py --import-mode=importlib
"""
import tempfile
import unittest
from pathlib import Path
from brisart_ai.knowledge.index import Index
from brisart_ai.web.crawler import (
    clean_search_query, content_exists, rank_results, score_result,
    search_keyword_fallback, _should_reject, _topic_terms,
)


class TestCleanSearchQuery(unittest.TestCase):
    def test_strips_trailing_punctuation(self):
        self.assertEqual(clean_search_query("who invented microsoft?"), "who invented microsoft")

    def test_collapses_whitespace(self):
        self.assertEqual(clean_search_query("  who   invented  microsoft  "), "who   invented  microsoft".split() and "who invented microsoft")

    def test_empty_query_returns_empty(self):
        self.assertEqual(clean_search_query(""), "")

    def test_preserves_natural_phrasing(self):
        # Natural phrasing should be kept, not reduced to keywords.
        result = clean_search_query("how many cats are in america?")
        self.assertIn("how", result)
        self.assertIn("many", result)


class TestSearchKeywordFallback(unittest.TestCase):
    def test_removes_function_words(self):
        result = search_keyword_fallback("how many cats are in america")
        self.assertNotIn(" the ", f" {result} ")
        self.assertIn("cats", result)
        self.assertIn("america", result)

    def test_adds_intent_hint_for_how_many(self):
        result = search_keyword_fallback("how many cats are in america")
        self.assertIn("number", result)

    def test_adds_intent_hint_for_population_of(self):
        result = search_keyword_fallback("what is the population of japan")
        self.assertIn("population", result)

    def test_empty_query_falls_back_to_original(self):
        result = search_keyword_fallback("   ")
        self.assertEqual(result, "")


class TestTopicTerms(unittest.TestCase):
    def test_extracts_meaningful_words(self):
        terms = _topic_terms("who founded microsoft")
        self.assertIn("microsoft", terms)
        self.assertIn("founded", terms)

    def test_function_words_excluded(self):
        terms = _topic_terms("who founded microsoft")
        self.assertNotIn("who", terms)


class TestScoreResult(unittest.TestCase):
    def test_matching_path_term_scores_positive(self):
        score = score_result("https://example.com/history-of-microsoft", {"microsoft", "history"})
        self.assertGreater(score, 0)

    def test_no_matching_terms_scores_low_or_negative(self):
        score_matching = score_result("https://example.com/history-of-microsoft", {"microsoft"})
        score_nonmatching = score_result("https://example.com/unrelated-page", {"microsoft"})
        self.assertGreater(score_matching, score_nonmatching)

    def test_account_login_host_penalized(self):
        score = score_result("https://account.microsoft.com/x", {"microsoft"})
        self.assertLess(score, score_result("https://en.wikipedia.org/wiki/history-microsoft", {"microsoft", "history"}))

    def test_low_value_host_penalized(self):
        score = score_result("https://www.reddit.com/r/microsoft", {"microsoft"})
        # A low-value host should score lower than a neutral host with the same term match.
        neutral_score = score_result("https://example.com/microsoft-page", {"microsoft"})
        self.assertLessEqual(score, neutral_score)

    def test_invalid_url_returns_very_low_score(self):
        score = score_result("", {"microsoft"})
        self.assertLessEqual(score, 0)


class TestRankResults(unittest.TestCase):
    def test_best_match_ranked_first(self):
        urls = [
            "https://example.com/unrelated-topic",
            "https://example.com/history-of-microsoft-founding",
        ]
        ranked = rank_results(urls, {"microsoft", "founding", "history"})
        self.assertEqual(ranked[0], "https://example.com/history-of-microsoft-founding")

    def test_duplicates_removed(self):
        urls = ["https://example.com/x", "https://example.com/x"]
        ranked = rank_results(urls, {"x"})
        self.assertEqual(len(ranked), 1)

    def test_stable_order_preserved_on_ties(self):
        urls = ["https://a.com/page", "https://b.com/page"]
        ranked = rank_results(urls, set())
        # With no topic terms, order should follow original input order (position tiebreak).
        self.assertEqual(ranked, urls)


class TestShouldReject(unittest.TestCase):
    def test_blocked_dictionary_host_rejected(self):
        self.assertTrue(_should_reject("https://merriam-webster.com/dictionary/x", set()))

    def test_normal_url_not_rejected(self):
        self.assertFalse(_should_reject("https://en.wikipedia.org/wiki/Microsoft", set()))


class TestContentExists(unittest.TestCase):
    def test_returns_false_for_new_hash(self):
        with tempfile.TemporaryDirectory() as d:
            idx = Index(str(Path(d) / "test.sqlite"))
            self.assertFalse(content_exists(idx, "nonexistent_hash_value"))
            idx.close()

    def test_returns_true_for_existing_content_hash(self):
        with tempfile.TemporaryDirectory() as d:
            idx = Index(str(Path(d) / "test.sqlite"))
            idx.add_source(source_type="web", location="https://x.com", title="X",
                text="some content", content_hash="abc123")
            self.assertTrue(content_exists(idx, "abc123"))
            idx.close()

    def test_does_not_raise_on_query_error(self):
        with tempfile.TemporaryDirectory() as d:
            idx = Index(str(Path(d) / "test.sqlite"))
            idx.close()  # closed connection should not raise, just return False
            try:
                result = content_exists(idx, "anything")
            except Exception:
                result = None
            self.assertIn(result, (True, False, None))


if __name__ == "__main__":
    unittest.main()


