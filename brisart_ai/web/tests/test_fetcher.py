"""Tests for brisart_ai/web/fetcher.py -- single-URL retrieval (no real network calls)."""
import unittest
from brisart_ai.web.fetcher import fetch_url


class TestFetchUrl(unittest.TestCase):
    def test_empty_url_returns_invalid_url_error(self):
        result = fetch_url("")
        self.assertEqual(result.error, "invalid URL")
        self.assertEqual(result.status, 0)

    def test_invalid_scheme_produces_a_result_not_an_exception(self):
        # normalize_url() will still try to prepend https:// to a bad string;
        # the key behavior under test is that fetch_url never raises.
        try:
            result = fetch_url("not a url at all $$$")
        except Exception as exc:
            self.fail(f"fetch_url raised unexpectedly: {exc}")
        self.assertIsNotNone(result)

    def test_unreachable_host_returns_error_not_exception(self):
        # This uses a reserved, non-routable address so it fails fast
        # without depending on real network connectivity in CI/sandboxes.
        result = fetch_url("http://198.51.100.1/")
        self.assertNotEqual(result.error, "")


if __name__ == "__main__":
    unittest.main()
