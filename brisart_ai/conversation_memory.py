class ConversationMemory:
    def __init__(self, max_items=20):
        self.max_items = max_items
        self.history = []

    def add_user(self, text):
        self.history.append(("user", text))
        self._trim()

    def add_ai(self, text):
        self.history.append(("ai", text))
        self._trim()

    def recent(self, count=5):
        return self.history[-count:]

    def summary(self):
        if not self.history:
            return "No conversation history."

        recent = self.recent()
        return " | ".join([msg for _, msg in recent])

    def _trim(self):
        if len(self.history) > self.max_items:
            self.history = self.history[-self.max_items:]