import tempfile
import unittest
from pathlib import Path

from brisart_ai.drive_scanner import scan_and_ingest, scan_preview
from brisart_ai.index import Index
from brisart_ai.recommender import recommend
from brisart_ai.ranker import search


class ScanRecommendTests(unittest.TestCase):
    def test_scan_preview_and_recommend(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "README.md").write_text("BrisartAI scans local research data and recommends actions.", encoding="utf-8")
            (root / "notes.log").write_text("archive archive preservation fixity", encoding="utf-8")
            preview = scan_preview([str(root)])
            self.assertIn("Candidate files", preview)
            db = root / "index.sqlite3"
            index = Index(str(db))
            try:
                count = scan_and_ingest([str(root)], index)
                self.assertEqual(count, 2)
                docs = search(index, "preservation")
                self.assertTrue(docs)
                recs = recommend(index)
                self.assertIn("BrisartAI Recommendations", recs)
            finally:
                index.close()


if __name__ == "__main__":
    unittest.main()
