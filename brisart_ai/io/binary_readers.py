"""
File: brisart_ai/io/binary_readers.py

Purpose
-------
Pure-Python, best-effort text extraction for Word/PowerPoint/Excel/ODT/PDF.

Communication / relationships
------------------------------
- brisart_ai/io/readers.py: read_file() dispatches here.
- Imports brisart_ai.native.brisart_inflate.brisart_zlib_decompress()
  (replacing zlib.decompress() for PDF content streams) -- see
  native/README.md for verification.

Settings / parameters
----------------------
- read_pdf_best_effort(path, max_bytes=10_000_000).

Edge cases
----------
- Office formats are zip containers; each reader unzips relevant parts.
- read_pdf_best_effort() finds literal parenthesized runs, then
  DEFLATE-decompresses stream...endstream blocks via brisart_zlib_decompress().
- Every function returns "" on any failure rather than raising.

Known limitations
-----------------
- Each reader is a minimal, dependency-free unzip/XML text scrape, not a
  full office-format parser; complex layouts, embedded objects, and
  styling are ignored -- only extractable text is returned.
- read_pdf_best_effort() is explicitly best-effort: encrypted, scanned,
  or heavily compressed PDFs may yield little or no text (no OCR).
- A corrupt or unsupported container returns "" rather than raising.

Examples
--------
    >>> text = read_docx("report.docx")          # -> plain text body
    >>> text = read_xlsx("data.xlsx")            # -> tab/newline joined cells
    >>> read_pdf_best_effort("missing.pdf")
    ''
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from brisart_ai.native.brisart_inflate import brisart_zlib_decompress


def _xml_text(xml_bytes: bytes) -> str:
    try:
        root = ElementTree.fromstring(xml_bytes)
    except Exception:
        return ""
    parts = []
    for node in root.iter():
        if node.text and node.text.strip():
            parts.append(node.text.strip())
    return "\n".join(parts)


def read_docx(path: Path) -> str:
    parts = []
    try:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.startswith("word/") and name.endswith(".xml"):
                    text = _xml_text(archive.read(name))
                    if text:
                        parts.append(text)
    except Exception:
        return ""
    return "\n".join(parts)


def read_pptx(path: Path) -> str:
    parts = []
    try:
        with zipfile.ZipFile(path) as archive:
            for name in sorted(archive.namelist()):
                if name.startswith("ppt/slides/") and name.endswith(".xml"):
                    text = _xml_text(archive.read(name))
                    if text:
                        parts.append(text)
                elif name.startswith("ppt/notesSlides/") and name.endswith(".xml"):
                    text = _xml_text(archive.read(name))
                    if text:
                        parts.append(text)
    except Exception:
        return ""
    return "\n".join(parts)


def read_xlsx(path: Path) -> str:
    parts = []
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "xl/sharedStrings.xml" in names:
                text = _xml_text(archive.read("xl/sharedStrings.xml"))
                if text:
                    parts.append(text)
            for name in sorted(names):
                if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                    text = _xml_text(archive.read(name))
                    if text:
                        parts.append(text)
    except Exception:
        return ""
    return "\n".join(parts)


def read_odt(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            if "content.xml" in archive.namelist():
                return _xml_text(archive.read("content.xml"))
    except Exception:
        return ""
    return ""


def read_pdf_best_effort(path: Path, max_bytes: int = 10_000_000) -> str:
    try:
        raw = path.read_bytes()[:max_bytes]
    except Exception:
        return ""
    chunks = []
    for match in re.finditer(rb"\((?:\\.|[^\\)])*\)", raw):
        value = match.group(0)[1:-1]
        value = value.replace(rb"\\(", b"(").replace(rb"\\)", b")").replace(rb"\\n", b"\n")
        decoded = value.decode("utf-8", "replace")
        if decoded.strip():
            chunks.append(decoded.strip())
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.DOTALL):
        stream = match.group(1).strip(b"\r\n")
        try:
            inflated = brisart_zlib_decompress(stream)
        except Exception:
            continue
        for text_match in re.finditer(rb"\((?:\\.|[^\\)])*\)", inflated):
            value = text_match.group(0)[1:-1]
            value = value.replace(rb"\\(", b"(").replace(rb"\\)", b")").replace(rb"\\n", b"\n")
            decoded = value.decode("utf-8", "replace")
            if decoded.strip():
                chunks.append(decoded.strip())
    text = "\n".join(chunks)
    text = re.sub(r"\s+", " ", text).strip()
    return text



