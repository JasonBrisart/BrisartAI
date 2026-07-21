import unittest

from brisart_ai.input_cleaner import normalize_shellish_input
from brisart_ai.self_knowledge import looks_like_self_question, self_response


class ChatUXTests(unittest.TestCase):
    def test_strip_shell_ask_inside_chat(self):
        self.assertEqual(normalize_shellish_input('py brisartai.py ask "hello"'), 'hello')

    def test_strip_shell_status_inside_chat(self):
        self.assertEqual(normalize_shellish_input('py brisartai.py status'), '/status')

    def test_typo_alias(self):
        self.assertEqual(normalize_shellish_input('statys'), 'status')

    def test_self_question(self):
        self.assertTrue(looks_like_self_question('what do you do for a living'))
        answer = self_response('what do you do for a living')
        self.assertIn('What I do:', answer)


if __name__ == '__main__':
    unittest.main()
