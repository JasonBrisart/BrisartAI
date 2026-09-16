"""
File: brisart_ai/web/tests/test_stats.py

Purpose
-------
Unit tests for brisart_ai.web.stats. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 3 test cases across TestCrawlStats.

Communication / relationships
------------------------------
- exercises brisart_ai.web.stats (CrawlStats)

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
- asserts: defaults are zero.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/web/tests/test_stats.py -v
    $ python -m pytest brisart_ai/web/tests/test_stats.py --import-mode=importlib
"""
import io
import unittest
from contextlib import redirect_stdout
from brisart_ai.web.stats import CrawlStats


class TestCrawlStats(unittest.TestCase):
    def test_defaults_are_zero(self):
        s = CrawlStats()
        self.assertEqual(s.requested, 0)
        self.assertEqual(s.indexed, 0)
        self.assertEqual(s.skipped_duplicates, 0)
        self.assertEqual(s.skipped_empty, 0)
        self.assertEqual(s.errors, 0)

    def test_fields_can_be_incremented(self):
        s = CrawlStats()
        s.requested += 5
        s.indexed += 3
        self.assertEqual(s.requested, 5)
        self.assertEqual(s.indexed, 3)

    def test_print_summary_includes_all_counters(self):
        s = CrawlStats(requested=10, indexed=7, skipped_duplicates=1, skipped_empty=1, errors=1)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            s.print_summary()
        output = buffer.getvalue()
        self.assertIn("Requested: 10", output)
        self.assertIn("Indexed: 7", output)
        self.assertIn("Duplicates: 1", output)
        self.assertIn("Empty pages: 1", output)
        self.assertIn("Errors: 1", output)


if __name__ == "__main__":
    unittest.main()



