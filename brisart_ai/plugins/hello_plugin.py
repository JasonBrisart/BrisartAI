"""Example plugin for BrisartAI."""

from __future__ import annotations

from brisart_ai.plugins.plugin_base import BrisartPlugin


class HelloPlugin(BrisartPlugin):
    """Provide a basic command for verifying the plugin system."""

    name = "Hello Plugin"
    version = "1.0.0"

    def description(self) -> str:
        """Return a description of the plugin."""
        return "Example plugin used to verify BrisartAI plugin loading."

    def commands(self) -> dict[str, object]:
        """Return commands exposed by this plugin."""
        return {
            "/hello": self.say_hello,
        }

    def say_hello(self) -> str:
        """Return the plugin greeting."""
        return "Hello from a BrisartAI plugin."


PLUGIN = HelloPlugin()