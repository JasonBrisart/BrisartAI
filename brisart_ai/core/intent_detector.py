class IntentDetector:

    GREETING = "greeting"
    STATUS = "status"
    QUESTION = "question"
    COMMAND = "command"
    CHAT = "chat"

    @staticmethod
    def detect(text):

        text = text.lower().strip()

        greetings = [
            "hi",
            "hello",
            "hey",
            "sup",
            "yo",
            "hl"
        ]

        if text in greetings:
            return IntentDetector.GREETING

        if any(x in text for x in [
            "status",
            "what's going on",
            "whats going on",
            "system status"
        ]):
            return IntentDetector.STATUS

        if text.startswith("/"):
            return IntentDetector.COMMAND

        if text.endswith("?"):
            return IntentDetector.QUESTION

        return IntentDetector.CHAT