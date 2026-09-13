"""
File: brisart_ai/io/readers.py

Purpose
-------
File-type dispatch for local ingestion. is_supported() decides which
files BrisartAI can read at all; iter_supported_files() walks a mix of
individual paths and folders (recursively, de-duplicated by resolved
path) to find them; read_file() extracts searchable text from any one
supported file, delegating to io/binary_readers.py for
.docx/.pptx/.xlsx/.odt/.pdf and io/extractor.py for .html/.csv, with a
few lighter-weight formats (.json, .jsonl, .rtf, .tsv) handled inline
here.

Communication / relationships
------------------------------
- brisart_ai/knowledge/ingest.py: calls iter_supported_files() and
  read_file() for every local import run.
- Calls brisart_ai.io.binary_readers.{read_docx,read_pptx,read_xlsx,
  read_odt,read_pdf_best_effort}, brisart_ai.io.extractor.{html_to_text,
  csv_to_text}, and brisart_ai.util.safe_read_text().

Settings / parameters
----------------------
- TEXT_EXTENSIONS / BINARY_TEXT_EXTENSIONS / SUPPORTED_EXTENSIONS: the
  full set of file extensions BrisartAI can ingest; SUPPORTED_EXTENSIONS
  is their union and is what is_supported() actually checks against.
- SUPPORTED_EXTENSIONLESS_NAMES: well-known extensionless filenames
  ("dockerfile", "makefile", "license", "readme", "changelog"), matched
  case-insensitively, so a repo's LICENSE or Dockerfile is still ingested
  even without a file extension.

Edge cases
----------
- iter_supported_files() silently skips anything it can't resolve or
  access (a bad path, or a permission error mid-walk) rather than
  aborting the whole ingestion run; a resolved-path set (`seen`)
  prevents the same file being yielded twice when it's reachable via
  more than one of the input paths.
- .rtf gets a deliberately crude regex stripper (_rtf_to_text) -- not a
  real RTF parser, just enough to make prose searchable.
- .json/.jsonl are pretty-printed when parseable via _pretty_json() and
  returned as-is (raw text) otherwise; this function never raises on
  invalid JSON.
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
    ".txt", ".md", ".markdown", ".rst", ".py", ".pyw", ".html", ".htm",
    ".csv", ".tsv", ".log", ".ini", ".cfg", ".conf", ".toml", ".xml",
    ".svg", ".yaml", ".yml", ".json", ".jsonl", ".ndjson", ".css",
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".java", ".c", ".h",
    ".cpp", ".hpp", ".cc", ".cs", ".go", ".rs", ".sh", ".bash", ".zsh",
    ".ps1", ".bat", ".cmd", ".sql", ".tex", ".rtf", ".srt", ".vtt",
    ".properties", ".env", ".gitignore", ".dockerfile",
}

BINARY_TEXT_EXTENSIONS = {".docx", ".pptx", ".xlsx", ".odt", ".pdf"}

SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | BINARY_TEXT_EXTENSIONS

# Well-known extensionless filenames, matched case-insensitively.
SUPPORTED_EXTENSIONLESS_NAMES = {
    "dockerfile", "makefile", "license", "readme", "changelog",
}


def is_supported(path: Path) -> bool:
    suffix = path.suffix.lower()
    name = path.name.lower()
    return (
        suffix in SUPPORTED_EXTENSIONS
        or name in SUPPORTED_EXTENSIONLESS_NAMES
    )


def iter_supported_files(paths: Iterable[str]) -> Iterator[Path]:
    """Yield supported files from a mix of individual paths and folders."""
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
            for child in path.rglob("*"):
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
        return json.dumps(parsed, indent=2, sort_keys=True, ensure_ascii=False)
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
