"""Local file readers for BrisartAI.

All readers use the Python standard library. Complex container formats are
handled with best-effort text extraction rather than perfect rendering.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Iterator

from brisart_ai.io.binary_readers import (
    read_docx,
    read_odt,
    read_pdf_best_effort,
    read_pptx,
    read_xlsx,
)
from brisart_ai.io.extractor import csv_to_text, html_to_text
from brisart_ai.util import safe_read_text

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".rst",
    ".py",
    ".pyw",
    ".html",
    ".htm",
    ".csv",
    ".tsv",
    ".log",
    ".ini",
    ".cfg",
    ".conf",
    ".toml",
    ".xml",
    ".svg",
    ".yaml",
    ".yml",
    ".json",
    ".jsonl",
    ".ndjson",
    ".css",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cc",
    ".cs",
    ".go",
    ".rs",
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
    ".bat",
    ".cmd",
    ".sql",
    ".tex",
    ".rtf",
    ".srt",
    ".vtt",
    ".properties",
    ".env",
    ".gitignore",
    ".dockerfile",
}
BINARY_TEXT_EXTENSIONS = {
    ".docx",
    ".pptx",
    ".xlsx",
    ".odt",
    ".pdf",
}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | BINARY_TEXT_EXTENSIONS
SUPPORTED_EXTENSIONLESS_NAMES = {
    "dockerfile",
    "makefile",
    "license",
    "readme",
    "changelog",
}


def is_supported(path: Path) -> bool:
    """Return whether BrisartAI has a reader for the supplied path."""
    suffix = path.suffix.lower()
    name = path.name.lower()
    return (
        suffix in SUPPORTED_EXTENSIONS
        or name in SUPPORTED_EXTENSIONLESS_NAMES
    )


def iter_supported_files(paths: Iterable[str]) -> Iterator[Path]:
    """Yield supported files from individual paths and folders."""
    seen = set()
    for raw in paths:
        path = Path(raw).expanduser()
        try:
            path = path.resolve()
        except OSError:
            continue
        if path.is_file():
            if is_supported(path) and path not in seen:
                seen.add(path)
                yield path
            continue
        if not path.is_dir():
            continue
        try:
            children = path.rglob("*")
            for child in children:
                try:
                    if child.is_file() and is_supported(child):
                        resolved = child.resolve()
                        if resolved not in seen:
                            seen.add(resolved)
                            yield resolved
                except (OSError, PermissionError):
                    continue
        except (OSError, PermissionError):
            continue


def _pretty_json(raw: str) -> str:
    try:
        parsed = json.loads(raw)
        return json.dumps(
            parsed,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
    except (json.JSONDecodeError, TypeError):
        return raw


def _rtf_to_text(raw: str) -> str:
    raw = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
    raw = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", raw)
    raw = raw.replace("{", " ").replace("}", " ")
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def read_file(path: Path) -> str:
    """Extract searchable text from one supported file."""
    ext = path.suffix.lower()
    if ext == ".docx":
        return read_docx(path)
    if ext == ".pptx":
        return read_pptx(path)
    if ext == ".xlsx":
        return read_xlsx(path)
    if ext == ".odt":
        return read_odt(path)
    if ext == ".pdf":
        return read_pdf_best_effort(path)
    raw = safe_read_text(path)
    if ext in {".html", ".htm", ".svg"}:
        _title, text, _links = html_to_text(raw)
        return text
    if ext == ".csv":
        return csv_to_text(raw)
    if ext == ".tsv":
        return raw.replace("\t", " | ")
    if ext == ".json":
        return _pretty_json(raw)
    if ext in {".jsonl", ".ndjson"}:
        lines = []
        for line in raw.splitlines():
            line = line.strip()
            if line:
                lines.append(_pretty_json(line))
        return "\n".join(lines)
    if ext == ".rtf":
        return _rtf_to_text(raw)
    return raw