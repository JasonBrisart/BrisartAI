"""
File: brisart_ai/web/tests/test_models.py

Purpose
-------
Unit tests for brisart_ai.web.models. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 3 test cases across TestFetchResult.

Communication / relationships
------------------------------
- exercises brisart_ai.web.models (FetchResult)

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
- asserts: error field defaults to empty string.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/web/tests/test_models.py -v
    $ python -m pytest brisart_ai/web/tests/test_models.py --import-mode=importlib
"""
import unittest
from brisart_ai.web.models import FetchResult


class TestFetchResult(unittest.TestCase):
    def test_construction_with_required_fields(self):
        r = FetchResult(url="https://x.com", status=200, content_type="text/html",
                         title="Title", text="body text", links=["https://x.com/a"])
        self.assertEqual(r.url, "https://x.com")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.error, "")

    def test_error_field_defaults_to_empty_string(self):
        r = FetchResult(url="https://x.com", status=0, content_type="", title="", text="", links=[])
        self.assertEqual(r.error, "")

    def test_error_can_be_set_explicitly(self):
        r = FetchResult(url="https://x.com", status=404, content_type="", title="", text="", links=[], error="HTTP 404")
        self.assertEqual(r.error, "HTTP 404")


if __name__ == "__main__":
    unittest.main()



