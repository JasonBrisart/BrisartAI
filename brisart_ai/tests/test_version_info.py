"""
File: brisart_ai/tests/test_version_info.py

Purpose
-------
Unit tests for brisart_ai.version_info. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 3 test cases across TestVersionInfo.

Communication / relationships
------------------------------
- exercises brisart_ai.version_info (APP_NAME, __version__)

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
- asserts: version is nonempty string.
- asserts: version not the unknown fallback when file exists.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/tests/test_version_info.py -v
    $ python -m pytest brisart_ai/tests/test_version_info.py --import-mode=importlib
"""
import unittest
from brisart_ai.version_info import APP_NAME, __version__


class TestVersionInfo(unittest.TestCase):
    def test_app_name_is_brisartai(self):
        self.assertEqual(APP_NAME, "BrisartAI")

    def test_version_is_nonempty_string(self):
        self.assertIsInstance(__version__, str)
        self.assertTrue(len(__version__) > 0)

    def test_version_not_the_unknown_fallback_when_file_exists(self):
        # version.txt exists in this package tree, so it should be read,
        # not fall back to "0.0.0-unknown".
        self.assertNotEqual(__version__, "0.0.0-unknown")


if __name__ == "__main__":
    unittest.main()



