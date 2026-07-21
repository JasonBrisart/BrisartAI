"""Local file readers for BrisartAI.

Everything here is pure Python standard library. For complex binary formats,
BrisartAI extracts best-effort searchable text rather than perfect rendering.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from .binary_readers import read_docx, read_odt, read_pdf_best_effort, read_pptx, read_xlsx
from .extractor import csv_to_text, html_to_text
from .util import safe_read_text

TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".py", ".pyw", ".html", ".htm",
    ".csv", ".tsv", ".log", ".ini", ".cfg", ".conf", ".toml",
    ".xml", ".svg", ".yaml", ".yml", ".json", ".jsonl", ".ndjson",
    ".css", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".java", ".c", ".h", ".cpp", ".hpp", ".cc", ".cs", ".go", ".rs",
    ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd", ".sql", ".tex",
    ".rtf", ".srt", ".vtt", ".properties", ".env", ".gitignore", ".dockerfile",
}

BINARY_TEXT_EXTENSIONS = {".docx", ".pptx", ".xlsx", ".odt", ".pdf"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | BINARY_TEXT_EXTENSIONS


def is_supported(path: Path) -> bool:
    if not path.is_file():
        # For tests and policy checks, accept a suffix even if file does not exist.
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            return True
        return path.name.lower() in {"dockerfile", "makefile", "license", "readme", "changelog"}
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_EXTENSIONS:
        return True
    return path.name.lower() in {"dockerfile", "makefile", "license", "readme", "changelog"}


def iter_supported_files(paths: Iterable[str]):
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if path.is_file() and is_supported(path):
            yield path
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and is_supported(child):
                    yield child


def _pretty_json(raw: str) -> str:
    try:
        parsed = json.loads(raw)
        return json.dumps(parsed, indent=2, sort_keys=True, ensure_ascii=False)
    except Exception:
        return raw


def _rtf_to_text(raw: str) -> str:
    raw = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
    raw = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", raw)
    raw = raw.replace("{", " ").replace("}", " ")
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def read_file(path: Path) -> str:
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
    if ext in {".json", ".jsonl", ".ndjson"}:
        if ext == ".json":
            return _pretty_json(raw)
        lines = []
        for line in raw.splitlines():
            line = line.strip()
            if line:
                lines.append(_pretty_json(line))
        return "\n".join(lines)
    if ext == ".rtf":
        return _rtf_to_text(raw)
    return raw
