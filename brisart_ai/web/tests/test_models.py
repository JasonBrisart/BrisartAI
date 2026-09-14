"""Tests for brisart_ai/web/models.py -- FetchResult."""
import unittest
from brisart_ai.web.models import FetchResult


class TestFetchResult(unittest.TestCase):
    def test_construction_with_required_fields(self):
        r = FetchResult(url="https://x.com", status=200, content_type="text/html",
                         title="Title", text="body text", links=["https://x.com/a"])
        self.assertEqual(r.url, "https://x.com")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.error, "")

    def test_error_field_defaults_to_empty_string(self):
        r = FetchResult(url="https://x.com", status=0, content_type="", title="", text="", links=[])
        self.assertEqual(r.error, "")

    def test_error_can_be_set_explicitly(self):
        r = FetchResult(url="https://x.com", status=404, content_type="", title="", text="", links=[], error="HTTP 404")
        self.assertEqual(r.error, "HTTP 404")


if __name__ == "__main__":
    unittest.main()
