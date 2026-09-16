"""
File: brisart_ai/ui/tests/test_theme.py

Purpose
-------
Unit tests for brisart_ai.ui. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 8 test cases across TestThemeConstants.

Communication / relationships
------------------------------
- exercises brisart_ai.ui (theme)

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
- asserts: background colors are hex strings.
- asserts: foreground colors are hex strings.
- asserts: border color is hex string.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/ui/tests/test_theme.py -v
    $ python -m pytest brisart_ai/ui/tests/test_theme.py --import-mode=importlib
"""
import unittest
from brisart_ai.ui import theme


class TestThemeConstants(unittest.TestCase):
    def test_background_colors_are_hex_strings(self):
        for attr in ("BG_APP", "BG_PANEL", "BG_SIDEBAR", "BG_INPUT", "BG_CHAT"):
            value = getattr(theme, attr)
            self.assertTrue(value.startswith("#"), msg=f"{attr} should be a hex color")
            self.assertEqual(len(value), 7, msg=f"{attr} should be #RRGGBB format")

    def test_foreground_colors_are_hex_strings(self):
        for attr in ("FG_TEXT", "FG_MUTED", "FG_ACCENT", "FG_ACCENT_DIM", "FG_SUCCESS",
                     "FG_WARN", "FG_USER", "FG_ASSISTANT", "FG_SYSTEM"):
            value = getattr(theme, attr)
            self.assertTrue(value.startswith("#"))

    def test_border_color_is_hex_string(self):
        self.assertTrue(theme.BORDER.startswith("#"))

    def test_font_tuples_have_family_and_size(self):
        for attr in ("FONT_UI", "FONT_UI_BOLD", "FONT_HEADING", "FONT_MONO", "FONT_MONO_BOLD"):
            value = getattr(theme, attr)
            self.assertIsInstance(value, tuple)
            self.assertGreaterEqual(len(value), 2)
            self.assertIsInstance(value[0], str)  # font family name
            self.assertIsInstance(value[1], int)  # font size

    def test_bold_fonts_have_bold_style(self):
        self.assertIn("bold", theme.FONT_UI_BOLD)
        self.assertIn("bold", theme.FONT_MONO_BOLD)
        self.assertIn("bold", theme.FONT_HEADING)

    def test_spacing_constants_are_positive_integers(self):
        self.assertIsInstance(theme.PAD, int)
        self.assertIsInstance(theme.PAD_SMALL, int)
        self.assertGreater(theme.PAD, 0)
        self.assertGreater(theme.PAD_SMALL, 0)
        self.assertGreater(theme.PAD, theme.PAD_SMALL)

    def test_sidebar_width_is_positive_integer(self):
        self.assertIsInstance(theme.SIDEBAR_WIDTH, int)
        self.assertGreater(theme.SIDEBAR_WIDTH, 0)

    def test_module_has_no_tk_import(self):
        # theme.py should be importable without any display / Tk dependency.
        import sys
        self.assertIn("brisart_ai.ui.theme", sys.modules)
        # No tkinter symbols should have been pulled in as a side effect
        # of importing this specific module (it's pure constants).
        module = sys.modules["brisart_ai.ui.theme"]
        self.assertFalse(hasattr(module, "tk"))


if __name__ == "__main__":
    unittest.main()


