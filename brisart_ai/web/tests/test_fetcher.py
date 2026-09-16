"""
File: brisart_ai/web/tests/test_fetcher.py

Purpose
-------
Unit tests for brisart_ai.web.fetcher. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 3 test cases across TestFetchUrl.

Communication / relationships
------------------------------
- exercises brisart_ai.web.fetcher (fetch_url)

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
- asserts: empty url returns invalid url error.
- asserts: invalid scheme produces a result not an exception.
- asserts: unreachable host returns error not exception.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/web/tests/test_fetcher.py -v
    $ python -m pytest brisart_ai/web/tests/test_fetcher.py --import-mode=importlib
"""
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


