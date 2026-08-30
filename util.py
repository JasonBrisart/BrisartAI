"""brisart_ai/util.py

Small, dependency-free utilities used everywhere: stopword-aware
tokenization, sentence splitting, URL normalization, stable hashing
(content dedup and source keys), file hashing (change detection), and
best-effort text decoding. Pure stdlib, so every other module can
depend on this without pulling in anything heavier.

`split_sentences()` only keeps sentences 30-700 characters long --
shorter is usually a heading/bullet/splitter artifact, longer is usually
several run-on sentences that would unfairly dominate answer-sentence
scoring in knowledge/synthesizer.py. `normalize_url()` always drops the
URL fragment (`#...`), since page content doesn't depend on it and
keeping it would make the same page look like multiple distinct
sources. `safe_read_text()` tries utf-8, then utf-16, then latin-1, and
falls back to utf-8 with `errors="replace"` if all three fail --
guaranteed to return a string, never raise, for any bytes content.
`file_hash()` streams in 1 MiB chunks so hashing a large file doesn't
hold the whole thing in memory.
"""
from __future__ import annotations

import hashlib
import re
import time
import urllib.parse
from pathlib import Path
from typing import List

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "he", "her", "his", "i", "in", "is", "it", "its",
    "me", "my", "of", "on", "or", "our", "she", "that", "the",
    "their", "them", "they", "this", "to", "was", "we", "were",
    "what", "when", "where", "which", "who", "why", "will", "with",
    "you", "your", "how", "about", "into", "over", "under", "can",
    "could", "should", "would", "not", "no", "yes", "do", "does",
    "did", "than", "then", "there", "here", "if", "so", "like",
    "file", "files", "data", "using", "use", "used", "also", "may",
    "one", "two",
}

WORD_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_\-]{1,}")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def now_ts() -> int:
    return int(time.time())


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tokenize(text: str) -> List[str]:
    words = [w.lower() for w in WORD_RE.findall(text or "")]
    return [w for w in words if len(w) > 1 and w not in STOPWORDS]


def split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    out = []
    for sentence in SENTENCE_RE.split(text):
        sentence = sentence.strip()
        if 30 <= len(sentence) <= 700:
            out.append(sentence)
    return out


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parsed = urllib.parse.urlsplit(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = urllib.parse.urlsplit(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    path = urllib.parse.quote(urllib.parse.unquote(path), safe="/%:@")
    return urllib.parse.urlunsplit((scheme, netloc, path, parsed.query, ""))


def same_site(a: str, b: str) -> bool:
    return urllib.parse.urlsplit(a).netloc.lower() == urllib.parse.urlsplit(b).netloc.lower()


def safe_read_text(path: Path, max_bytes: int = 5_000_000) -> str:
    raw = path.read_bytes()[:max_bytes]
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding, "replace")
        except Exception:
            continue
    return raw.decode("utf-8", "replace")
