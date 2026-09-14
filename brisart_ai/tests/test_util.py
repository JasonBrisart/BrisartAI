"""Tests for brisart_ai/util.py -- shared tokenize/hash/URL/sentence toolbox."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from brisart_ai.util import file_hash, normalize_url, same_site, split_sentences, stable_hash, tokenize


class TestTokenize(unittest.TestCase):
    def test_basic_tokenization(self):
        self.assertEqual(tokenize("Hello, World! Co-founder"), ["hello", "world", "co-founder"])

    def test_stopwords_removed(self):
        tokens = tokenize("the cat and the dog")
        self.assertNotIn("the", tokens)
        self.assertNotIn("and", tokens)
        self.assertIn("cat", tokens)
        self.assertIn("dog", tokens)

    def test_none_input_returns_empty_list(self):
        self.assertEqual(tokenize(None), [])

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(tokenize(""), [])

    def test_single_char_words_excluded(self):
        tokens = tokenize("a b I x")
        self.assertEqual(tokens, [])


class TestStableHash(unittest.TestCase):
    def test_matches_real_hashlib_sha256(self):
        value = "test string with café unicode"
        expected = hashlib.sha256(value.encode("utf-8")).hexdigest()
        self.assertEqual(stable_hash(value), expected)

    def test_deterministic(self):
        self.assertEqual(stable_hash("same input"), stable_hash("same input"))

    def test_different_inputs_differ(self):
        self.assertNotEqual(stable_hash("a"), stable_hash("b"))


class TestFileHash(unittest.TestCase):
    def test_matches_hashlib_for_file_contents(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.txt"
            content = b"file content for hashing" * 100
            path.write_bytes(content)
            expected = hashlib.sha256(content).hexdigest()
            self.assertEqual(file_hash(path), expected)

    def test_streams_large_file_correctly(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "large.bin"
            content = bytes((i % 256) for i in range(3 * 1024 * 1024))  # 3MB, spans multiple 1MB chunks
            path.write_bytes(content)
            expected = hashlib.sha256(content).hexdigest()
            self.assertEqual(file_hash(path), expected)


class TestSplitSentences(unittest.TestCase):
    def test_splits_on_sentence_boundaries(self):
        text = "This is one sentence that is long enough to pass the length filter here. " \
               "This is another sentence that is also long enough to pass the filter here."
        sentences = split_sentences(text)
        self.assertEqual(len(sentences), 2)

    def test_too_short_sentences_dropped(self):
        text = "Hi. " + "A" * 50 + " sentence long enough to pass through the length filter here today."
        sentences = split_sentences(text)
        self.assertTrue(all(len(s) >= 30 for s in sentences))

    def test_empty_text_returns_empty_list(self):
        self.assertEqual(split_sentences(""), [])

    def test_none_returns_empty_list(self):
        self.assertEqual(split_sentences(None), [])


class TestNormalizeUrl(unittest.TestCase):
    def test_empty_string_returns_empty(self):
        self.assertEqual(normalize_url(""), "")

    def test_schemeless_url_gets_https_prepended(self):
        self.assertEqual(normalize_url("example.com/x"), "https://example.com/x")

    def test_scheme_and_host_lowercased(self):
        result = normalize_url("HTTPS://Example.COM/A")
        self.assertTrue(result.startswith("https://example.com"))

    def test_path_percent_encoding_normalized(self):
        result = normalize_url("https://example.com/A%20b")
        self.assertIn("%20", result)

    def test_fragment_stripped(self):
        result = normalize_url("https://example.com/x#fragment")
        self.assertNotIn("#", result)


class TestSameSite(unittest.TestCase):
    def test_same_host_different_scheme_is_same_site(self):
        self.assertTrue(same_site("http://a.com/x", "https://a.com/y"))

    def test_different_hosts_not_same_site(self):
        self.assertFalse(same_site("http://a.com", "http://b.com"))

    def test_case_insensitive_comparison(self):
        self.assertTrue(same_site("http://Example.com", "http://example.COM"))


if __name__ == "__main__":
    unittest.main()
