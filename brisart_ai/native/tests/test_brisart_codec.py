"""
File: brisart_ai/native/tests/test_brisart_codec.py

Purpose
-------
Unit tests for brisart_ai.native.brisart_codec. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 8 test cases across TestBrisartBase64.

Communication / relationships
------------------------------
- exercises brisart_ai.native.brisart_codec (brisart_b64decode, brisart_b64encode, brisart_urlsafe_b64decode)

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
- asserts: missing padding is tolerated.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/native/tests/test_brisart_codec.py -v
    $ python -m pytest brisart_ai/native/tests/test_brisart_codec.py --import-mode=importlib
"""
import base64
import unittest
from brisart_ai.native.brisart_codec import brisart_b64decode, brisart_b64encode, brisart_urlsafe_b64decode


class TestBrisartBase64(unittest.TestCase):
    def test_encode_matches_stdlib_rfc4648_vectors(self):
        for text in (b"", b"f", b"fo", b"foo", b"foob", b"fooba", b"foobar"):
            self.assertEqual(brisart_b64encode(text), base64.b64encode(text), msg=f"input={text!r}")

    def test_decode_matches_stdlib(self):
        for text in (b"", b"Zg==", b"Zm8=", b"Zm9v", b"Zm9vYg==", b"Zm9vYmE=", b"Zm9vYmFy"):
            self.assertEqual(brisart_b64decode(text), base64.b64decode(text), msg=f"input={text!r}")

    def test_round_trip_random_bytes(self):
        import random
        rng = random.Random(42)
        for _ in range(20):
            data = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 200)))
            encoded = brisart_b64encode(data)
            self.assertEqual(encoded, base64.b64encode(data))
            self.assertEqual(brisart_b64decode(encoded), data)

    def test_urlsafe_encoding_matches_stdlib(self):
        data = b"\xfb\xff\xfe subject/data+more"
        self.assertEqual(brisart_b64encode(data, urlsafe=True), base64.urlsafe_b64encode(data))

    def test_missing_padding_is_tolerated(self):
        # Bing's redirect wrapper strips '=' padding entirely.
        real_url = b"https://en.wikipedia.org/wiki/Microsoft"
        encoded_with_padding = base64.urlsafe_b64encode(real_url)
        stripped = encoded_with_padding.rstrip(b"=").decode("ascii")
        self.assertEqual(brisart_urlsafe_b64decode(stripped), real_url)

    def test_decode_accepts_str_input(self):
        self.assertEqual(brisart_b64decode("Zm9vYmFy"), b"foobar")

    def test_invalid_character_raises_value_error(self):
        with self.assertRaises(ValueError):
            brisart_b64decode("not valid base64 !!!")

    def test_empty_round_trip(self):
        self.assertEqual(brisart_b64encode(b""), b"")
        self.assertEqual(brisart_b64decode(b""), b"")


if __name__ == "__main__":
    unittest.main()



