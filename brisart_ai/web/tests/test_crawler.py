import unittest
from brisart_ai.web.crawler import (
    clean_search_query, rank_results, score_result, search_keyword_fallback, _topic_terms,
)


class TestCleanSearchQuery(unittest.TestCase):
    def test_strips_trailing_punctuation(self):
        self.assertEqual(clean_search_query("who invented microsoft?"), "who invented microsoft")

    def test_empty_query_returns_empty(self):
        self.assertEqual(clean_search_query(""), "")


class TestSearchKeywordFallback(unittest.TestCase):
    def test_removes_function_words(self):
        result = search_keyword_fallback("how many cats are in america")
        self.assertIn("cats", result)
        self.assertIn("america", result)

    def test_adds_intent_hint_for_how_many(self):
        result = search_keyword_fallback("how many cats are in america")
        self.assertIn("number", result)


class TestTopicTerms(unittest.TestCase):
    def test_extracts_meaningful_words(self):
        terms = _topic_terms("who founded microsoft")
        self.assertIn("microsoft", terms)
        self.assertIn("founded", terms)


class TestScoreResultBackwardCompatible(unittest.TestCase):
    """score_result/_score_detail must behave EXACTLY as before when no
    snippet is supplied -- snippet is purely additive."""

    def test_matching_path_term_scores_positive(self):
        score = score_result("https://example.com/history-of-microsoft", {"microsoft", "history"})
        self.assertGreater(score, 0)

    def test_no_snippet_argument_is_backward_compatible(self):
        with_default = score_result("https://example.com/history-of-microsoft", {"microsoft"}, "who founded microsoft", "History of Microsoft")
        with_explicit_empty = score_result("https://example.com/history-of-microsoft", {"microsoft"}, "who founded microsoft", "History of Microsoft", "")
        self.assertEqual(with_default, with_explicit_empty)


class TestScoreResultSnippetAware(unittest.TestCase):
    """The actual fix: a snippet-only term match now contributes to the
    score, but weighted BELOW a title match."""

    def test_snippet_only_match_scores_positive(self):
        # "france" appears only in the snippet, not in the URL/title.
        score_with_snippet = score_result(
            "https://en.wikipedia.org/wiki/Paris", {"capital", "france"},
            title="Paris - Wikipedia",
            snippet="Paris is the capital and most populous city of France.",
        )
        score_without_snippet = score_result(
            "https://en.wikipedia.org/wiki/Paris", {"capital", "france"},
            title="Paris - Wikipedia",
        )
        self.assertGreater(score_with_snippet, score_without_snippet)

    def test_snippet_only_match_weighted_below_title_match(self):
        # Same term ("microsoft"), once matched only via snippet and once
        # matched via title -- the title match must score higher.
        snippet_only = score_result(
            "https://example.com/some-page", {"microsoft"},
            title="Some Page", snippet="This page mentions microsoft in passing.",
        )
        title_match = score_result(
            "https://example.com/some-page", {"microsoft"},
            title="Some Page About Microsoft", snippet="",
        )
        self.assertLess(snippet_only, title_match)


class TestRankResultsWithSnippets(unittest.TestCase):
    def test_entity_answer_page_ranks_above_irrelevant_decoy_with_snippet_FIX(self):
        urls = [
            "https://example.com/unrelated-page",
            "https://en.wikipedia.org/wiki/Paris",
        ]
        titles = {
            "https://example.com/unrelated-page": "Some Unrelated Page",
            "https://en.wikipedia.org/wiki/Paris": "Paris - Wikipedia",
        }
        snippets = {
            "https://en.wikipedia.org/wiki/Paris":
                "Paris is the capital and most populous city of France.",
        }
        ranked = rank_results(
            urls, {"capital", "france"}, "what is the capital of france",
            titles=titles, snippets=snippets,
        )
        self.assertEqual(ranked[0], "https://en.wikipedia.org/wiki/Paris")

    def test_rank_results_without_snippets_arg_is_backward_compatible(self):
        urls = ["https://example.com/a", "https://example.com/history-of-microsoft"]
        titles = {"https://example.com/history-of-microsoft": "History of Microsoft"}
        with_snippets_none = rank_results(urls, {"microsoft", "history"}, "", titles=titles)
        with_snippets_omitted = rank_results(urls, {"microsoft", "history"}, "", titles=titles, snippets=None)
        self.assertEqual(with_snippets_none, with_snippets_omitted)


if __name__ == "__main__":
    unittest.main()
