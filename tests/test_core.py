import tempfile
import unittest
from pathlib import Path

from brisart_ai.index import Index
from brisart_ai.ingest import ingest_paths
from brisart_ai.ranker import search
from brisart_ai.util import normalize_url, tokenize


class CoreTests(unittest.TestCase):
    def test_tokenize(self):
        self.assertEqual(tokenize("The research archive stores files"), ["research", "archive", "stores"])

    def test_normalize_url(self):
        self.assertEqual(normalize_url("example.com"), "https://example.com/")

    def test_ingest_and_search(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "note.md").write_text("BrisartAI indexes local research archives.", encoding="utf-8")
            db = folder / "test.sqlite3"
            index = Index(str(db))
            try:
                count = ingest_paths([str(folder)], index)
                self.assertEqual(count, 1)
                docs = search(index, "local research archives")
                self.assertTrue(docs)
            finally:
                index.close()


if __name__ == "__main__":
    unittest.main()
