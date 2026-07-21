class StateManager:

    def __init__(self, index):

        self.index = index

    def build_status(self):

        docs = len(self.index.documents)
        chunks = len(self.index.fragments)

        return {
            "documents": docs,
            "fragments": chunks,
            "knowledge_loaded": docs > 0
        }

    def format_status(self):

        info = self.build_status()

        return (
            "\nBrisartAI Status\n"
            "\nImported Documents: "
            + str(info["documents"])
            + "\nKnowledge Fragments: "
            + str(info["fragments"])
            + "\nKnowledge Loaded: "
            + str(info["knowledge_loaded"])
        )