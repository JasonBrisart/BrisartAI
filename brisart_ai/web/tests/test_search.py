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


class TestIsSearchHost(unittest.TestCase):
    def test_bing_is_search_host(self):
        self.assertTrue(_is_search_host("www.bing.com"))

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

    def test_entity_answer_page_dropped_without_snippet_2tuple(self):
        # "Paris - Wikipedia" shares NO token with "capital"/"france", and
        # a bare (url, title) pair (no snippet) has nothing else to check
        # against -- this is the documented boundary of the fix, not a
        # regression: without a snippet, there is nothing to fold in.
        results = [("https://en.wikipedia.org/wiki/Paris", "Paris - Wikipedia")]
        related, unrelated = _partition_related_results("what is the capital of france", results)
        self.assertEqual(len(related), 0)
        self.assertEqual(len(unrelated), 1)

    def test_entity_answer_page_kept_with_snippet_3tuple_FIX(self):
        # The actual fix: once the provider's own snippet/description text
        # is captured and passed through as a 3-tuple, the entity-answer
        # page is correctly recognized as related, exactly as a real
        # search engine's own results page would show it.
        results = [(
            "https://en.wikipedia.org/wiki/Paris",
            "Paris - Wikipedia",
            "Paris is the capital and most populous city of France.",
        )]
        related, unrelated = _partition_related_results("what is the capital of france", results)
        self.assertEqual(len(related), 1, "FIX VERIFIED: snippet text rescues the entity-answer page")
        self.assertEqual(len(unrelated), 0)

    def test_inventor_entity_answer_kept_with_snippet_FIX(self):
        results = [(
            "https://en.wikipedia.org/wiki/Alexander_Graham_Bell",
            "Alexander Graham Bell - Wikipedia",
            "Alexander Graham Bell was a Scottish-born inventor, scientist, "
            "and engineer who is credited with patenting the first practical telephone.",
        )]
        related, unrelated = _partition_related_results("who invented the telephone", results)
        self.assertEqual(len(related), 1)
        self.assertEqual(len(unrelated), 0)


if __name__ == "__main__":
    unittest.main()
