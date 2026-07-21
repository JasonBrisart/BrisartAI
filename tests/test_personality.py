import unittest

from brisart_ai.personality import confidence_label, opening
from brisart_ai.synthesizer import synthesize


class PersonalityTests(unittest.TestCase):
    def test_confidence_labels(self):
        self.assertEqual(confidence_label(0), "unknown")
        self.assertEqual(confidence_label(1), "low")
        self.assertEqual(confidence_label(5), "moderate")
        self.assertEqual(confidence_label(9), "high")

    def test_opening(self):
        self.assertIn("reviewed 2 indexed sources", opening("answer", 2))

    def test_synthesizer_voice(self):
        docs = [{
            "source_type": "file",
            "title": "README.md",
            "location": "/tmp/README.md",
            "text": "BrisartAI scans local research data. BrisartAI gives recommendations from indexed evidence.",
        }]
        answer = synthesize("local research recommendations", docs)
        self.assertIn("Observation:", answer)
        self.assertIn("Why I think this:", answer)
        self.assertIn("Suggested next move:", answer)


if __name__ == "__main__":
    unittest.main()
