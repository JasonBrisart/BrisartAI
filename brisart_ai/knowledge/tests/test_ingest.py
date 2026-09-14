"""Tests for brisart_ai/knowledge/ingest.py -- ingest_paths()."""
import tempfile
import unittest
from pathlib import Path
from brisart_ai.knowledge.index import Index
from brisart_ai.knowledge.ingest import ingest_paths


class TestIngestPaths(unittest.TestCase):
    def test_ingests_supported_files_in_folder(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.txt").write_text("hello world")
            (root / "b.md").write_text("markdown content")
            idx = Index(str(root / "idx.sqlite"))
            count = ingest_paths([str(root)], idx)
            self.assertEqual(count, 2)
            idx.close()

    def test_skips_empty_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "empty.txt").write_text("   ")
            (root / "real.txt").write_text("actual content here")
            idx = Index(str(root / "idx.sqlite"))
            count = ingest_paths([str(root)], idx)
            self.assertEqual(count, 1)
            idx.close()

    def test_unsupported_extension_not_ingested(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "image.png").write_bytes(b"\x89PNG")
            idx = Index(str(root / "idx.sqlite"))
            count = ingest_paths([str(root)], idx)
            self.assertEqual(count, 0)
            idx.close()

    def test_single_file_path(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            f = root / "single.txt"
            f.write_text("single file content")
            idx = Index(str(root / "idx.sqlite"))
            count = ingest_paths([str(f)], idx)
            self.assertEqual(count, 1)
            idx.close()

    def test_returns_zero_for_nonexistent_path(self):
        with tempfile.TemporaryDirectory() as d:
            idx = Index(str(Path(d) / "idx.sqlite"))
            count = ingest_paths(["/nonexistent/path"], idx)
            self.assertEqual(count, 0)
            idx.close()


if __name__ == "__main__":
    unittest.main()
