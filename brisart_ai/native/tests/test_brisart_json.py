"""
File: brisart_ai/native/tests/test_brisart_json.py

Purpose
-------
Unit tests for brisart_ai.native.brisart_json. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 12 test cases across TestBrisartJsonLoads, TestBrisartJsonDumps.

Communication / relationships
------------------------------
- exercises brisart_ai.native.brisart_json (BrisartJSONDecodeError, brisart_dumps, brisart_loads)

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
- asserts: primitives match stdlib.
- asserts: nested structure matches stdlib.
- asserts: unicode escape matches stdlib.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/native/tests/test_brisart_json.py -v
    $ python -m pytest brisart_ai/native/tests/test_brisart_json.py --import-mode=importlib
"""
import json
import unittest
from brisart_ai.native.brisart_json import BrisartJSONDecodeError, brisart_dumps, brisart_loads


class TestBrisartJsonLoads(unittest.TestCase):
    def test_primitives_match_stdlib(self):
        for text in ("null", "true", "false", "42", "-3.14", '"hello"'):
            self.assertEqual(brisart_loads(text), json.loads(text))

    def test_nested_structure_matches_stdlib(self):
        text = '{"a": [1, 2, {"b": "c"}], "d": null, "e": true}'
        self.assertEqual(brisart_loads(text), json.loads(text))

    def test_unicode_escape_matches_stdlib(self):
        text = '"\\u00e9\\u00e8"'
        self.assertEqual(brisart_loads(text), json.loads(text))

    def test_surrogate_pair_matches_stdlib(self):
        text = '"\\ud83d\\ude00"'  # 😀 emoji as a UTF-16 surrogate pair
        self.assertEqual(brisart_loads(text), json.loads(text))

    def test_malformed_json_raises_decode_error(self):
        with self.assertRaises(BrisartJSONDecodeError):
            brisart_loads("{invalid")

    def test_malformed_json_is_a_value_error(self):
        # Mirrors json.JSONDecodeError being a ValueError subclass.
        self.assertTrue(issubclass(BrisartJSONDecodeError, ValueError))

    def test_duplicate_keys_last_one_wins(self):
        self.assertEqual(brisart_loads('{"a": 1, "a": 2}'), {"a": 2})
        self.assertEqual(brisart_loads('{"a": 1, "a": 2}'), json.loads('{"a": 1, "a": 2}'))


class TestBrisartJsonDumps(unittest.TestCase):
    def test_sort_keys_matches_stdlib(self):
        data = {"b": 1, "a": 2}
        self.assertEqual(brisart_dumps(data, sort_keys=True), json.dumps(data, sort_keys=True))

    def test_indented_output_matches_stdlib_structure(self):
        data = {"x": [1, 2, {"y": "z"}]}
        ours = brisart_dumps(data, indent=2, sort_keys=True)
        theirs = json.dumps(data, indent=2, sort_keys=True)
        # Re-parse both to confirm structural equivalence (formatting may differ trivially).
        self.assertEqual(brisart_loads(ours), json.loads(theirs))

    def test_round_trip_preserves_data(self):
        data = {"nested": [1, 2.5, "text", None, True, False, {"k": "v"}]}
        self.assertEqual(brisart_loads(brisart_dumps(data)), data)

    def test_non_ascii_round_trips_correctly(self):
        # BrisartJSON emits raw UTF-8 (not \\uXXXX escapes) for non-ASCII --
        # a deliberate, documented difference from json.dumps's default
        # ensure_ascii=True. Both are valid JSON; only the data must match.
        data = {"title": "café article"}
        dumped = brisart_dumps(data)
        self.assertEqual(brisart_loads(dumped), data)
        self.assertEqual(json.loads(dumped), data)

    def test_special_floats_not_emitted_for_ordinary_values(self):
        self.assertEqual(brisart_dumps(3.14), "3.14")


if __name__ == "__main__":
    unittest.main()


