"""
File: brisart_ai/knowledge/tests/test_ingest.py

Purpose
-------
Unit tests for brisart_ai.knowledge.ingest. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 5 test cases across TestIngestPaths.

Communication / relationships
------------------------------
- exercises brisart_ai.knowledge.index (Index)
- exercises brisart_ai.knowledge.ingest (ingest_paths)

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
- asserts: skips empty files.
- asserts: unsupported extension not ingested.
- asserts: single file path.
- asserts: returns zero for nonexistent path.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/knowledge/tests/test_ingest.py -v
    $ python -m pytest brisart_ai/knowledge/tests/test_ingest.py --import-mode=importlib
"""
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


