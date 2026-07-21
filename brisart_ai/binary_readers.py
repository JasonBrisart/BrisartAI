"""Pure-Python best-effort readers for common container formats.

These readers use only the Python standard library. They are intentionally
simple and inspectable. They do not try to perfectly reproduce Office/PDF
rendering. They extract useful searchable text when possible.
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
