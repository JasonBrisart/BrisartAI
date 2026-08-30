"""brisart_ai/io/binary_readers.py

Pure-Python, best-effort text extraction for Word (.docx), PowerPoint
(.pptx), Excel (.xlsx), OpenDocument Text (.odt), and PDF (.pdf) --
stdlib only (zipfile, xml.etree, re, zlib), no third-party parsing
libraries. The goal throughout is searchable text, not faithful visual
rendering, so these are intentionally simple.

The Office formats (.docx/.pptx/.xlsx/.odt) are zip containers holding
XML parts; each reader just unzips the relevant parts (Word: all of
word/*.xml; PowerPoint: slides AND notes slides, so speaker notes are
searchable too; Excel: sharedStrings.xml plus every worksheet; ODT:
content.xml) and pulls text nodes out with ElementTree.

PDF is the odd one out: `read_pdf_best_effort()` is a hand-rolled,
non-rendering scraper that finds literal parenthesized text runs
directly in the raw bytes, then separately zlib-decompresses any
`stream...endstream` block it can (the common case for modern PDF
content streams) and pulls parenthesized runs out of that too. It makes
no attempt to reconstruct reading order or layout.

Every function here returns an empty string on any failure (corrupt
zip, malformed XML, undecompressable stream) rather than raising --
callers already treat empty text as "nothing to index," so one bad file
never blocks an import run.
"""
from __future__ import annotations

import re
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree


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
            inflated = zlib.decompress(stream)
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
