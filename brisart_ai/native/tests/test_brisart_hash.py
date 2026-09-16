"""
File: brisart_ai/native/tests/test_brisart_hash.py

Purpose
-------
Unit tests for brisart_ai.native.brisart_hash. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 11 test cases across TestBrisartHash256.

Communication / relationships
------------------------------
- exercises brisart_ai.native.brisart_hash (BrisartHash256, brisart_sha256, brisart_stable_hash)

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
- asserts: empty input matches hashlib.
- asserts: short input matches hashlib.
- asserts: matches hashlib across block boundaries.
- asserts: streaming update matches single call.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/native/tests/test_brisart_hash.py -v
    $ python -m pytest brisart_ai/native/tests/test_brisart_hash.py --import-mode=importlib
"""
import hashlib
import unittest
from brisart_ai.native.brisart_hash import BrisartHash256, brisart_sha256, brisart_stable_hash


class TestBrisartHash256(unittest.TestCase):
    def test_empty_input_matches_hashlib(self):
        self.assertEqual(brisart_sha256(b"").hexdigest(), hashlib.sha256(b"").hexdigest())

    def test_short_input_matches_hashlib(self):
        self.assertEqual(brisart_sha256(b"abc").hexdigest(), hashlib.sha256(b"abc").hexdigest())

    def test_known_fips_vector(self):
        self.assertEqual(
            brisart_sha256(b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq").hexdigest(),
            hashlib.sha256(b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq").hexdigest(),
        )

    def test_matches_hashlib_across_block_boundaries(self):
        # 55/56/57/63/64/65-byte inputs exercise the single-block padding edge cases.
        for length in (0, 1, 55, 56, 57, 63, 64, 65, 128, 1000):
            data = bytes((i % 251) for i in range(length))
            self.assertEqual(
                brisart_sha256(data).hexdigest(), hashlib.sha256(data).hexdigest(),
                msg=f"mismatch at length={length}",
            )

    def test_non_ascii_string_matches_hashlib(self):
        text = "café \u00e9\u00e8 unicode test"
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.assertEqual(brisart_sha256(text.encode("utf-8")).hexdigest(), expected)

    def test_streaming_update_matches_single_call(self):
        data = b"the quick brown fox jumps over the lazy dog" * 50
        streamed = BrisartHash256()
        for i in range(0, len(data), 17):
            streamed.update(data[i:i+17])
        whole = brisart_sha256(data)
        self.assertEqual(streamed.hexdigest(), whole.hexdigest())
        self.assertEqual(streamed.hexdigest(), hashlib.sha256(data).hexdigest())

    def test_update_rejects_str(self):
        with self.assertRaises(TypeError):
            BrisartHash256().update("not bytes")

    def test_digest_and_block_size_attributes(self):
        self.assertEqual(BrisartHash256.digest_size, 32)
        self.assertEqual(BrisartHash256.block_size, 64)

    def test_copy_produces_independent_clone(self):
        h1 = brisart_sha256(b"hello")
        h2 = h1.copy()
        h2.update(b" world")
        self.assertNotEqual(h1.hexdigest(), h2.hexdigest())
        self.assertEqual(h2.hexdigest(), hashlib.sha256(b"hello world").hexdigest())

    def test_stable_hash_matches_manual_sha256(self):
        value = "a stable string"
        self.assertEqual(brisart_stable_hash(value), hashlib.sha256(value.encode("utf-8")).hexdigest())

    def test_hexdigest_is_64_hex_chars(self):
        d = brisart_sha256(b"anything").hexdigest()
        self.assertEqual(len(d), 64)
        int(d, 16)  # raises ValueError if not valid hex


if __name__ == "__main__":
    unittest.main()



