"""
File: brisart_ai/tests/test_util.py

Purpose
-------
Unit tests for brisart_ai.util. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 12 test cases across TestUtil.

Communication / relationships
------------------------------
- exercises brisart_ai.util (file_hash, normalize_url, same_site, split_sentences, stable_hash, tokenize)

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
- asserts: none.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/tests/test_util.py -v
    $ python -m pytest brisart_ai/tests/test_util.py --import-mode=importlib
"""
import tempfile, unittest
from pathlib import Path
from brisart_ai.util import (file_hash, normalize_url, same_site, split_sentences,
                             stable_hash, tokenize)
class TestUtil(unittest.TestCase):
    def test_tokenize(self): self.assertEqual(tokenize("Hello, World! Co-founder"), ["hello","world","co-founder"])
    def test_stopwords(self):
        t = tokenize("the cat and the dog"); self.assertNotIn("the", t); self.assertIn("cat", t)
    def test_none(self): self.assertEqual(tokenize(None), [])
    def test_stable_hash_deterministic(self): self.assertEqual(stable_hash("x"), stable_hash("x"))
    def test_stable_hash_64hex(self): self.assertEqual(len(stable_hash("x")), 64)
    def test_file_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"f.bin"; p.write_bytes(b"content"*1000)
            self.assertEqual(len(file_hash(p)), 64)
    def test_split_sentences(self):
        text = "This is one long sentence that clears the length filter easily here. And a second long sentence that also clears the length filter here."
        self.assertEqual(len(split_sentences(text)), 2)
    def test_split_empty(self): self.assertEqual(split_sentences(""), [])
    def test_normalize_url_scheme(self): self.assertTrue(normalize_url("example.com/x").startswith("https://example.com"))
    def test_normalize_url_lowercase(self): self.assertTrue(normalize_url("HTTPS://Example.COM/A").startswith("https://example.com"))
    def test_normalize_url_fragment(self): self.assertNotIn("#", normalize_url("https://example.com/x#frag"))
    def test_same_site(self): self.assertTrue(same_site("http://a.com/x","https://a.com/y")); self.assertFalse(same_site("http://a.com","http://b.com"))
if __name__ == "__main__": unittest.main()



