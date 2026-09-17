"""
File: brisart_ai/util.py

Purpose
-------
The one shared, dependency-free toolbox every other layer of BrisartAI
imports from: tokenization for the ranker and index, SHA-256 hashing for
stable source keys and file de-duplication, URL normalization and
same-site comparison for the crawler, sentence splitting for answer
synthesis, and best-effort multi-encoding text reading for local file
ingestion. Nothing here depends on any other brisart_ai module except
brisart_ai.native, which is what lets it sit at the very bottom of the
application's own import graph.

Communication / relationships
------------------------------
- brisart_ai/knowledge/index.py: now_ts(), stable_hash(), tokenize()
- brisart_ai/knowledge/ranker.py: tokenize()
- brisart_ai/knowledge/synthesizer.py: split_sentences(), tokenize()
- brisart_ai/knowledge/ingest.py: file_hash()
- brisart_ai/io/readers.py: safe_read_text()
- brisart_ai/io/extractor.py: normalize_url()
- brisart_ai/web/crawler.py: normalize_url(), same_site(), stable_hash()
- brisart_ai/core/session_memory.py: now_ts(), tokenize()
- Imports brisart_ai.native.brisart_hash.brisart_sha256() (replacing
  hashlib.sha256()) and brisart_ai.native.brisart_url's
  brisart_urlsplit()/brisart_urlunsplit()/brisart_quote()/
  brisart_unquote() (replacing the corresponding urllib.parse
  functions) -- see brisart_ai/native/README.md for how each of these
  was independently verified against the real stdlib function it
  replaces before being wired in here. Otherwise imports nothing from
  elsewhere in brisart_ai; only the standard library (re, time,
  pathlib) beyond that.

Settings / parameters
----------------------
- STOPWORDS: a small, English-only stopword set used by tokenize() to
  drop function words before terms are indexed or matched.
- WORD_RE: token boundary pattern for tokenize() -- alphanumerics plus
  internal underscores/hyphens, at least two characters.
- SENTENCE_RE: a lookbehind split on sentence-ending punctuation, used
  by split_sentences(); sentences outside the 30-700 character band
  are dropped.

Edge cases
----------
- tokenize(None) and tokenize("") both return [] rather than raising.
- file_hash() streams a file in 1 MB chunks rather than reading it
  whole, each chunk fed through BrisartHash256.update().
- safe_read_text() tries utf-8, then utf-16, then latin-1, and always
  succeeds via a final errors="replace" decode.
- normalize_url("") returns ""; normalize_url() on a schemeless string
  assumes https and prepends it before parsing.
- same_site() compares hostnames only (case-insensitively).
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import List

from brisart_ai.native.brisart_hash import brisart_sha256
from brisart_ai.native.brisart_url import (
    brisart_quote,
    brisart_unquote,
    brisart_urlsplit,
    brisart_urlunsplit,
)

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
    return brisart_sha256(value.encode("utf-8", "replace")).hexdigest()


def file_hash(path: Path) -> str:
    h = brisart_sha256(b"")
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
    parsed = brisart_urlsplit(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = brisart_urlsplit(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    path = brisart_quote(brisart_unquote(path), safe="/%:@")
    return brisart_urlunsplit(
        type(parsed)(scheme, netloc, path, parsed.query, "")
    )


def same_site(a: str, b: str) -> bool:
    return brisart_urlsplit(a).netloc.lower() == brisart_urlsplit(b).netloc.lower()


def safe_read_text(path: Path, max_bytes: int = 5_000_000) -> str:
    raw = path.read_bytes()[:max_bytes]
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding, "replace")
        except Exception:
            continue
    return raw.decode("utf-8", "replace")
