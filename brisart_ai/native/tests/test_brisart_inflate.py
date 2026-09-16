"""
File: brisart_ai/native/tests/test_brisart_inflate.py

Purpose
-------
Unit tests for brisart_ai.native.brisart_inflate. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 10 test cases across TestBrisartInflate.

Communication / relationships
------------------------------
- exercises brisart_ai.native.brisart_inflate (brisart_adler32, brisart_inflate, brisart_zlib_decompress)

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
- asserts: empty input round trip.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/native/tests/test_brisart_inflate.py -v
    $ python -m pytest brisart_ai/native/tests/test_brisart_inflate.py --import-mode=importlib
"""
import zlib
import unittest
from brisart_ai.native.brisart_inflate import brisart_adler32, brisart_inflate, brisart_zlib_decompress


class TestBrisartInflate(unittest.TestCase):
    def test_stored_block_round_trip(self):
        payload = b"Brisart"
        header = 0b00000001  # BFINAL=1, BTYPE=00 (stored)
        length = len(payload)
        nlen = (~length) & 0xFFFF
        stream = bytes([header]) + length.to_bytes(2, "little") + nlen.to_bytes(2, "little") + payload
        self.assertEqual(brisart_inflate(stream), payload)

    def test_decompresses_real_zlib_compressed_data_default_level(self):
        original = b"(Hello World) Tj (This is PDF content) Tj (" + b"A" * 500 + b") Tj"
        compressed = zlib.compress(original, level=9)
        self.assertEqual(brisart_zlib_decompress(compressed), original)

    def test_decompresses_larger_dynamic_huffman_content(self):
        original = (b"the quick brown fox jumps over the lazy dog " * 200)
        compressed = zlib.compress(original, level=6)
        self.assertEqual(brisart_zlib_decompress(compressed), original)

    def test_decompresses_incompressible_random_data(self):
        import random
        rng = random.Random(7)
        original = bytes(rng.randrange(256) for _ in range(4000))
        compressed = zlib.compress(original)
        self.assertEqual(brisart_zlib_decompress(compressed), original)

    def test_empty_input_round_trip(self):
        compressed = zlib.compress(b"")
        self.assertEqual(brisart_zlib_decompress(compressed), b"")

    def test_adler32_matches_zlib(self):
        for data in (b"", b"hello", b"the quick brown fox" * 100):
            self.assertEqual(brisart_adler32(data), zlib.adler32(data))

    def test_invalid_short_input_raises(self):
        with self.assertRaises(ValueError):
            brisart_zlib_decompress(b"\x00")

    def test_wrong_compression_method_raises(self):
        # First byte's low nibble must be 8 (DEFLATE); craft an invalid one
        # while keeping the header checksum congruent to 0 mod 31.
        bad = bytes([0x09, 0x00]) + b"\x00" * 6
        with self.assertRaises(ValueError):
            brisart_zlib_decompress(bad)

    def test_checksum_mismatch_raises_when_verified(self):
        original = b"hello world"
        compressed = bytearray(zlib.compress(original))
        compressed[-1] ^= 0xFF  # corrupt the trailing Adler-32 checksum
        with self.assertRaises(ValueError):
            brisart_zlib_decompress(bytes(compressed), verify_checksum=True)

    def test_checksum_mismatch_not_raised_when_unverified(self):
        original = b"hello world"
        compressed = bytearray(zlib.compress(original))
        compressed[-1] ^= 0xFF
        # Should not raise since checksum verification is disabled; content still decodes.
        result = brisart_zlib_decompress(bytes(compressed), verify_checksum=False)
        self.assertEqual(result, original)


if __name__ == "__main__":
    unittest.main()


