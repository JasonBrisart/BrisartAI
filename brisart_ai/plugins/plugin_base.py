"""Base plugin interface for BrisartAI."""

from __future__ import annotations

from typing import Callable, Dict


PluginCommand = Callable[..., object]


class BrisartPlugin:
    """Base class for BrisartAI plugins."""

    name = "Unnamed Plugin"
    version = "0.1.0"

    def description(self) -> str:
        """Return a human-readable plugin description."""

        return "No description provided."

    def commands(
        self,
    ) -> Dict[str, PluginCommand]:
        """Return commands exposed by the plugin."""

        return {}

    def on_startup(self) -> None:
        """Run optional plugin startup behavior."""

        return None

    def on_shutdown(self) -> None:
        """Run optional plugin shutdown behavior."""

        return None


__all__ = [
    "BrisartPlugin",
    "PluginCommand",
]
