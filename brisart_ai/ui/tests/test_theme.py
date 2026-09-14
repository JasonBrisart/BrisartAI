"""Tests for brisart_ai/ui/theme.py -- shared color palette and font tuples.

theme.py has no Tk imports and no side effects, so it is fully testable
without a display -- unlike app.py/chat_panel.py/dialogs.py/sidebar.py/
service.py's GUI classes, which require a live Tk display and are
exercised manually rather than under headless unit tests.
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
