import tempfile
import unittest
from pathlib import Path

from brisart_ai.freeform import freeform_response
from brisart_ai.index import Index
from brisart_ai.ingest import ingest_paths
from brisart_ai.ranker import search
from brisart_ai.readers import is_supported


class FreeformFileTypeTests(unittest.TestCase):
    def test_freeform_without_data(self):
        response = freeform_response("hello there")
        self.assertIn("BrisartAI", response)
        self.assertIn("Observation:", response)

    def test_more_file_types_supported(self):
        names = ["data.json", "script.js", "style.css", "notes.rtf", "sheet.xlsx", "slides.pptx", "doc.docx", "paper.pdf"]
        for name in names:
            self.assertTrue(is_supported(Path(name)), name)

    def test_ingest_json_and_search(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "data.json").write_text('{"project":"BrisartAI", "feature":"freeform responses"}', encoding="utf-8")
            db = folder / "index.sqlite3"
            index = Index(str(db))
            try:
                count = ingest_paths([str(folder)], index)
                self.assertEqual(count, 1)
                docs = search(index, "freeform responses")
                self.assertTrue(docs)
            finally:
                index.close()


if __name__ == "__main__":
    unittest.main()
