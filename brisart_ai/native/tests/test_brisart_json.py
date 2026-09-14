"""Tests for brisart_ai/native/brisart_json.py -- BrisartJSON vs. real json module."""
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
