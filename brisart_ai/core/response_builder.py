class ResponseBuilder:

    def greeting(self):

        return (
            "Hello Jason.\n\n"
            "BrisartAI is online and ready.\n"
            "You can chat normally, import data, "
            "crawl sources, or analyze information."
        )

    def no_data_chat(self, question):

        return (
            f"You asked: {question}\n\n"
            "I do not currently have any imported "
            "documents to ground my answer.\n\n"
            "I can still respond conversationally, "
            "but the response is not based on imported evidence."
        )

    def no_data_status(self):

        return (
            "Current assessment:\n\n"
            "- No imported documents\n"
            "- No indexed knowledge\n"
            "- Chat system active\n"
            "- Reasoning available\n\n"
            "Import files to unlock evidence-based responses."
        )