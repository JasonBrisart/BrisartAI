"""
File: brisart_ai/io/tests/test_input_cleaner.py

Purpose
-------
Unit tests for brisart_ai.io.input_cleaner. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 8 test cases across TestNormalizeShellishInput.

Communication / relationships
------------------------------
- exercises brisart_ai.io.input_cleaner (normalize_shellish_input)

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
- asserts: strips matching single quotes.
- asserts: mismatched quotes not stripped.
- asserts: inner quotes not touched.
- asserts: all whitespace returns empty.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/io/tests/test_input_cleaner.py -v
    $ python -m pytest brisart_ai/io/tests/test_input_cleaner.py --import-mode=importlib
"""
import unittest
from brisart_ai.io.input_cleaner import normalize_shellish_input


class TestNormalizeShellishInput(unittest.TestCase):
    def test_trims_whitespace(self):
        self.assertEqual(normalize_shellish_input("  hello  "), "hello")

    def test_strips_matching_double_quotes(self):
        self.assertEqual(normalize_shellish_input('"hello world"'), "hello world")

    def test_strips_matching_single_quotes(self):
        self.assertEqual(normalize_shellish_input("'hello world'"), "hello world")

    def test_mismatched_quotes_not_stripped(self):
        self.assertEqual(normalize_shellish_input("\"hello world'"), "\"hello world'")

    def test_inner_quotes_not_touched(self):
        # Only a single outer layer is stripped; quotes about quoted text
        # inside the string are untouched.
        result = normalize_shellish_input('say "hi" please')
        self.assertEqual(result, 'say "hi" please')

    def test_all_whitespace_returns_empty(self):
        self.assertEqual(normalize_shellish_input("   "), "")

    def test_empty_string_returns_empty(self):
        self.assertEqual(normalize_shellish_input(""), "")

    def test_plain_text_unchanged(self):
        self.assertEqual(normalize_shellish_input("stats"), "stats")


if __name__ == "__main__":
    unittest.main()


