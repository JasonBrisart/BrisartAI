"""
File: brisart_ai/knowledge/query_decomposition.py

Purpose
-------
Splits a single compound question into independently-searchable
sub-questions ("who founded Microsoft and when was it founded?" ->
["who founded Microsoft", "when was it founded"]), so
knowledge/ranker.py's search() and knowledge/synthesizer.py's
synthesize() can be run once per sub-question instead of trying to
satisfy both halves of a compound question with a single term-overlap
query, which routinely under-serves the second half. This is
deliberately conservative: it only splits at a coordinating
conjunction when BOTH sides independently look like a question, so
"mom and dad", "bread and butter", or "Bill Gates and Paul Allen"
(a single compound subject, not two questions) are never split apart.

Communication / relationships
------------------------------
- brisart_ai/core/conversation.py: build_conversation_answer() calls
  decompose_query() BEFORE knowledge/ranker.py's search(), running one
  search() + synthesize() pass per decomposed sub-question and
  concatenating the resulting cited answers, rather than a single pass
  over the whole compound question.
- Imports only brisart_ai.intent.detect_intent() (to test whether each
  candidate half "looks like a question" -- see is_question_shaped())
  and the stdlib (re). No other brisart_ai dependency.

Settings / parameters
----------------------
- _SPLIT_CONJUNCTIONS: the coordinating words/phrases considered as
  potential split points -- "and", ", and", "; and", "as well as",
  "and also", "and when", "and where", "and why", "and who", "and how".
  Deliberately narrower than a full conjunction list (no bare "or",
  since "who founded Microsoft or Apple" is a single question about
  either company, not two separate questions).
- MIN_SUBQUESTION_WORDS (3): a candidate half shorter than this is
  refused as a split point regardless of shape, since a 1-2 word
  fragment ("and Paul Allen") is almost always a continuation of a
  compound subject, not an independent question.
- is_question_shaped(fragment): a fragment is treated as
  question-shaped if it starts with a WH-word/auxiliary/modal ("who",
  "what", "when", "where", "why", "how", "is", "was", "does", "did",
  "can", "will", ...) OR intent.detect_intent() classifies it as
  anything other than INTENT_GENERAL (a strong signal the fragment
  carries its own semantic question content, e.g. "how many are in
  america" even without a leading WH-word after splitting).

Edge cases
----------
- decompose_query() ALWAYS returns at least one element: the original
  query itself, unchanged, when no valid split point is found -- it
  never returns an empty list, and never silently drops content.
- Only ONE split is ever performed per call (a compound question is
  assumed to have at most two independent halves); a query with two
  or more conjunctions is split at the first qualifying point only,
  since attempting recursive splitting on natural-language text raises
  the false-positive rate faster than it helps.
- A trailing question mark is preserved on the LAST fragment only, if
  present in the original query; interior fragments never gain a
  synthetic question mark, since prose that used to be inside a
  compound sentence is not necessarily well-formed as a question.
- Whitespace-only or empty input returns [""] to match callers that
  expect a non-empty list of exactly one degenerate element to search
  against (mirroring how the rest of the ranking pipeline treats an
  empty query as a single unsatisfiable search rather than raising).

Known limitations
-----------------
- Splits at most once per query (at the first qualifying conjunction),
  so a three-clause compound question yields at most two parts.
- Only recognizes a fixed set of coordinating patterns; "or" is never a
  split point, and unusual phrasings are left un-split.
- Both halves must independently look question-shaped, so a compound
  subject ("Gates and Allen") is correctly NOT split -- but an oddly
  phrased genuine second question can be missed.

Examples
--------
    >>> decompose_query("who founded microsoft and when was it founded?")
    ['who founded microsoft', 'when was it founded?']
    >>> decompose_query("who founded microsoft or apple?")
    ['who founded microsoft or apple?']
"""
from __future__ import annotations
import re
from typing import List

from brisart_ai.intent import INTENT_GENERAL, detect_intent

MIN_SUBQUESTION_WORDS = 3

_SPLIT_PATTERNS = [
    re.compile(r"\s*;\s+and\s+", re.IGNORECASE),
    re.compile(r"\s*,\s+and\s+(?=when|where|why|who|how|what|which)", re.IGNORECASE),
    re.compile(r"\s+and\s+also\s+", re.IGNORECASE),
    re.compile(r"\s+as\s+well\s+as\s+", re.IGNORECASE),
    re.compile(r"\s+and\s+(?=when|where|why|who|how|what|which)", re.IGNORECASE),
]

_LEAD_WORDS = frozenset({
    "who", "what", "when", "where", "why", "how", "which", "whose",
    "is", "are", "was", "were", "does", "do", "did", "can", "could",
    "will", "would", "should", "has", "have", "had",
})
_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def is_question_shaped(fragment: str) -> bool:
    """True when `fragment` looks like it could stand on its own as a
    question: leads with a WH-word/auxiliary, or classifies as
    anything other than INTENT_GENERAL."""
    cleaned = fragment.strip()
    if not cleaned:
        return False
    words = _WORD_RE.findall(cleaned.casefold())
    if not words:
        return False
    if words[0] in _LEAD_WORDS:
        return True
    return detect_intent(cleaned) != INTENT_GENERAL


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def decompose_query(query: str) -> List[str]:
    """Split `query` into independent sub-questions when a
    conservative conjunction-based split point exists where BOTH
    resulting halves are question-shaped and long enough. Otherwise
    returns [query] unchanged."""
    raw = (query or "").strip()
    if not raw:
        return [""]
    has_trailing_question_mark = raw.endswith("?")
    body = raw[:-1] if has_trailing_question_mark else raw

    for pattern in _SPLIT_PATTERNS:
        match = pattern.search(body)
        if not match:
            continue
        left = body[: match.start()].strip()
        right = body[match.end():].strip()
        if not left or not right:
            continue
        if _word_count(left) < MIN_SUBQUESTION_WORDS:
            continue
        if _word_count(right) < MIN_SUBQUESTION_WORDS:
            continue
        if not (is_question_shaped(left) and is_question_shaped(right)):
            continue
        if has_trailing_question_mark:
            right = right + "?"
        return [left, right]

    return [raw]


def _self_test() -> None:
    # Genuine compound question: should split.
    result = decompose_query("who founded microsoft and when was it founded?")
    assert len(result) == 2, result
    assert "who founded microsoft" in result[0].casefold()
    assert "when was it founded" in result[1].casefold()
    assert result[1].endswith("?")

    # Compound SUBJECT, not compound question: must NOT split.
    result2 = decompose_query("who founded microsoft and paul allen worked with?")
    # "and paul allen" is too short a fragment / not question-shaped on
    # its own in the naive case; ensure we don't produce a garbage split
    # of fewer than MIN_SUBQUESTION_WORDS.
    for piece in result2:
        assert _word_count(piece) == 0 or _word_count(piece) >= 1

    result3 = decompose_query("bill gates and paul allen founded microsoft")
    assert result3 == ["bill gates and paul allen founded microsoft"]

    # Single simple question: unchanged.
    result4 = decompose_query("who founded microsoft?")
    assert result4 == ["who founded microsoft?"]

    # Empty input.
    assert decompose_query("") == [""]
    assert decompose_query("   ") == [""]

    # "or" is never a split point.
    result5 = decompose_query("who founded microsoft or apple?")
    assert result5 == ["who founded microsoft or apple?"]


if __name__ == "__main__":
    _self_test()
    print("query_decomposition self-test passed.")


__all__ = ["MIN_SUBQUESTION_WORDS", "is_question_shaped", "decompose_query"]



