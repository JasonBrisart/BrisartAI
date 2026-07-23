"""BrisartAI command-line interface (compatibility shim).

The CLI was split into focused modules:
- commands.py : individual command handlers
- chat.py     : interactive shell
- cli.py      : argument parser and entry point

This file re-exports the public surface so existing imports such as
`from brisart_ai.core.assistant import cmd_chat, main` keep working.
"""
from __future__ import annotations

from brisart_ai.core.chat import cmd_chat
from brisart_ai.core.cli import build_parser, main
from brisart_ai.core.commands import (
    build_answer,
    cmd_analyze,
    cmd_ask,
    cmd_collection_add,
    cmd_collection_create,
    cmd_collection_list,
    cmd_crawl,
    cmd_ingest,
    cmd_note_add,
    cmd_note_list,
    cmd_note_search,
    cmd_project,
    cmd_recommend,
    cmd_research_report,
    cmd_scan,
    cmd_status,
    cmd_timeline,
    cmd_vault,
    cmd_vault_rebuild,
    cmd_web,
)

__all__ = [
    "build_answer",
    "build_parser",
    "cmd_analyze",
    "cmd_ask",
    "cmd_chat",
    "cmd_collection_add",
    "cmd_collection_create",
    "cmd_collection_list",
    "cmd_crawl",
    "cmd_ingest",
    "cmd_note_add",
    "cmd_note_list",
    "cmd_note_search",
    "cmd_project",
    "cmd_recommend",
    "cmd_research_report",
    "cmd_scan",
    "cmd_status",
    "cmd_timeline",
    "cmd_vault",
    "cmd_vault_rebuild",
    "cmd_web",
    "main",
]