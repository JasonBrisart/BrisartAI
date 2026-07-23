"""Pure-Python plugin discovery and loading for BrisartAI."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Dict

from brisart_ai.plugins.plugin_base import (
    BrisartPlugin,
    PluginCommand,
)


DEFAULT_PLUGIN_DIR = Path(__file__).resolve().parent


class PluginManager:
    """Discover, load, and manage BrisartAI plugins."""

    def __init__(
        self,
        plugin_dir: str | Path | None = None,
    ):
        if plugin_dir is None:
            self.plugin_dir = DEFAULT_PLUGIN_DIR
        else:
            self.plugin_dir = Path(
                plugin_dir
            ).expanduser().resolve()

        self.plugins: list[BrisartPlugin] = []

    def load_plugins(self) -> None:
        """Load plugin files containing a PLUGIN object."""

        self.plugins.clear()

        if not self.plugin_dir.exists():
            return

        if not self.plugin_dir.is_dir():
            print(
                "PLUGIN DIRECTORY INVALID: "
                f"{self.plugin_dir}"
            )
            return

        ignored_files = {
            "__init__.py",
            "manager.py",
            "plugin_base.py",
        }

        for path in sorted(
            self.plugin_dir.glob("*.py")
        ):
            if path.name in ignored_files:
                continue

            if path.name.startswith("_"):
                continue

            module_name = (
                "brisart_ai.plugins.dynamic_"
                + path.stem
            )

            try:
                specification = (
                    importlib.util.spec_from_file_location(
                        module_name,
                        path,
                    )
                )

                if (
                    specification is None
                    or specification.loader is None
                ):
                    print(
                        f"PLUGIN FAILED: {path.name}: "
                        "module specification unavailable"
                    )
                    continue

                module = importlib.util.module_from_spec(
                    specification
                )

                sys.modules[module_name] = module

                try:
                    specification.loader.exec_module(
                        module
                    )
                except Exception:
                    sys.modules.pop(
                        module_name,
                        None,
                    )
                    raise

                plugin = getattr(
                    module,
                    "PLUGIN",
                    None,
                )

                if plugin is None:
                    print(
                        f"PLUGIN SKIPPED: {path.name}: "
                        "no PLUGIN object"
                    )
                    continue

                if not isinstance(
                    plugin,
                    BrisartPlugin,
                ):
                    print(
                        f"PLUGIN FAILED: {path.name}: "
                        "PLUGIN must inherit BrisartPlugin"
                    )
                    continue

                plugin.on_startup()
                self.plugins.append(plugin)

                print(
                    f"PLUGIN LOADED: {plugin.name} "
                    f"{plugin.version}"
                )

            except Exception as exc:
                print(
                    f"PLUGIN FAILED: {path.name}: "
                    f"{exc}"
                )

    def commands(
        self,
    ) -> Dict[str, PluginCommand]:
        """Return the combined command registry."""

        result: Dict[
            str,
            PluginCommand,
        ] = {}

        for plugin in self.plugins:
            try:
                plugin_commands = (
                    plugin.commands()
                )
            except Exception as exc:
                print(
                    "PLUGIN COMMAND ERROR: "
                    f"{plugin.name}: {exc}"
                )
                continue

            if not isinstance(
                plugin_commands,
                dict,
            ):
                print(
                    "PLUGIN COMMAND ERROR: "
                    f"{plugin.name}: commands() "
                    "must return a dictionary"
                )
                continue

            for command_name, handler in (
                plugin_commands.items()
            ):
                cleaned_name = str(
                    command_name
                ).strip()

                if not cleaned_name:
                    continue

                if not callable(handler):
                    print(
                        "PLUGIN COMMAND ERROR: "
                        f"{plugin.name}: "
                        f"{cleaned_name} is not callable"
                    )
                    continue

                result[cleaned_name] = handler

        return result

    def run_command(
        self,
        command_name: str,
        *args,
        **kwargs,
    ):
        """Run one registered plugin command."""

        cleaned_name = str(
            command_name
        ).strip()

        command_registry = self.commands()
        handler = command_registry.get(
            cleaned_name
        )

        if handler is None:
            raise KeyError(
                "Unknown plugin command: "
                f"{cleaned_name}"
            )

        return handler(
            *args,
            **kwargs,
        )

    def shutdown(self) -> None:
        """Notify loaded plugins of shutdown."""

        for plugin in reversed(
            self.plugins
        ):
            try:
                plugin.on_shutdown()
            except Exception as exc:
                print(
                    "PLUGIN SHUTDOWN FAILED: "
                    f"{plugin.name}: {exc}"
                )

        self.plugins.clear()


__all__ = [
    "DEFAULT_PLUGIN_DIR",
    "PluginManager",
]
