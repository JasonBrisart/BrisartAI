"""
File: brisart_ai/knowledge/diversity.py

Purpose
-------
Re-orders an already-ranked result list so the top N results are not
all near-duplicates of each other -- five URLs that are all the same
Wikipedia mirror, or five sentences that all restate the same fact in
slightly different words, waste the user's attention budget compared
to five results that each add distinct information. Implements
Maximal Marginal Relevance (MMR): repeatedly pick the next result that
best balances (a) its original relevance score against (b) how
DIFFERENT it is from everything already selected, rather than always
taking the next-highest-scored result regardless of overlap.

Communication / relationships
------------------------------
- knowledge/ranker.py: search() calls diversify_results() as the final
  step over the already-scored candidate list, on every call -- strictly
  a re-ORDERING, never a re-scoring: every document that entered
  diversify_results() is still present in its output, just possibly in
  a different order, and the underlying score is never altered.
- Imports only brisart_ai.util.tokenize() (for the Jaccard-similarity
  fallback used when no host/location is available) and the stdlib.

Settings / parameters
----------------------
- DEFAULT_LAMBDA (0.7): MMR's relevance/diversity trade-off knob.
  1.0 would ignore diversity entirely (identical to the original
  ranked order); 0.0 would ignore relevance entirely and just
  maximize spread. 0.7 keeps relevance dominant while still visibly
  penalizing near-duplicates -- picked empirically as a middle ground
  that never reorders a CLEARLY best result out of first place (see
  the self-test), only affects ties and near-ties further down the
  list.
- similarity(doc_a, doc_b): two documents are considered similar to
  the extent that (a) they share the same host (SAME_HOST_PENALTY,
  0.5, applied once) plus (b) the Jaccard similarity of their title
  token sets. Host-level similarity is checked first and cheaply,
  since two pages from the same domain are a much stronger duplication
  signal than incidental title-word overlap.
- MAX_RESULTS: diversify_results() only re-orders the top
  `max_results` candidates (default: the length of the input list) --
  callers wanting diversity only within a top-K slice (e.g. top 10 of
  50 fetched candidates) can pass max_results=10 to cap the O(n^2)
  pairwise-similarity work to just that slice.

Edge cases
----------
- diversify_results() on an empty or single-element list returns it
  unchanged.
- A document missing both a location/host AND a title falls back to
  similarity 0.0 against everything (cannot be judged similar to
  anything), so it is never penalized for missing metadata.
- The FIRST result selected by diversify_results() is ALWAYS the
  single highest-scored input document, regardless of lambda -- MMR's
  first pick has no "already selected" set to diversify against, so it
  reduces to pure relevance by construction, not by a special case in
  this implementation.

Known limitations
-----------------
- document_similarity() combines only same-host detection and title-
  token Jaccard overlap; two near-duplicate bodies under different
  hosts and titles are not detected as similar.
- MMR is O(n^2) in the re-ordered slice; very large pools are costly.
- Pure re-ordering: it never re-scores or drops a document, so a
  genuinely redundant result can still appear lower in the list.

Examples
--------
    >>> ranked = [{"id":1,"score":10,"title":"History of Microsoft","location":"https://en.wikipedia.org/a"},
    ...           {"id":2,"score":9,"title":"History of Microsoft","location":"https://en.wikipedia.org/b"}]
    >>> [d["id"] for d in diversify_results(ranked, lambda_param=0.5)][0]
    1
"""
from __future__ import annotations
from typing import Callable, Dict, List, Sequence
from urllib.parse import urlsplit

from brisart_ai.util import tokenize

DEFAULT_LAMBDA = 0.7
SAME_HOST_PENALTY = 0.5


def _hostname(location: str) -> str:
    try:
        return (urlsplit(str(location or "")).hostname or "").casefold()
    except Exception:
        return ""


def _title_tokens(title: str) -> set:
    return set(tokenize(title or ""))


def jaccard_similarity(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return (intersection / union) if union else 0.0


def document_similarity(doc_a: Dict, doc_b: Dict) -> float:
    """Similarity in [0, 1] between two document dicts (expected keys:
    'location', 'title'). Same-host contributes SAME_HOST_PENALTY;
    title-token Jaccard similarity contributes the remainder, capped
    at 1.0 total."""
    host_a = _hostname(doc_a.get("location", ""))
    host_b = _hostname(doc_b.get("location", ""))
    host_score = SAME_HOST_PENALTY if (host_a and host_a == host_b) else 0.0
    title_score = (1.0 - SAME_HOST_PENALTY) * jaccard_similarity(
        _title_tokens(doc_a.get("title", "")), _title_tokens(doc_b.get("title", "")),
    )
    return min(1.0, host_score + title_score)


def diversify_results(
    ranked_documents: Sequence[Dict],
    lambda_param: float = DEFAULT_LAMBDA,
    max_results: int = None,
    similarity_fn: Callable[[Dict, Dict], float] = document_similarity,
) -> List[Dict]:
    """Re-order `ranked_documents` (each expected to carry a 'score'
    key, highest-first on input) using Maximal Marginal Relevance.
    Returns a NEW list; does not mutate the input or any document's
    score."""
    documents = list(ranked_documents)
    if len(documents) <= 1:
        return documents
    limit = len(documents) if max_results is None else max(1, min(max_results, len(documents)))

    remaining = list(documents)
    selected: List[Dict] = []

    # First pick: always the single highest-scored document.
    remaining.sort(key=lambda d: d.get("score", 0.0), reverse=True)
    selected.append(remaining.pop(0))

    while remaining and len(selected) < limit:
        best_index = None
        best_mmr_score = None
        for index, candidate in enumerate(remaining):
            relevance = candidate.get("score", 0.0)
            max_similarity_to_selected = max(
                (similarity_fn(candidate, chosen) for chosen in selected),
                default=0.0,
            )
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity_to_selected
            if best_mmr_score is None or mmr_score > best_mmr_score:
                best_mmr_score = mmr_score
                best_index = index
        selected.append(remaining.pop(best_index))

    # Any documents beyond `limit` are appended unchanged, preserving
    # their original relative order, so the function never DROPS input.
    selected.extend(remaining)
    return selected


def _self_test() -> None:
    assert diversify_results([]) == []
    single = [{"score": 1.0, "title": "A", "location": "https://a.com"}]
    assert diversify_results(single) == single

    docs = [
        {"id": 1, "score": 10.0, "title": "History of Microsoft", "location": "https://en.wikipedia.org/wiki/Microsoft"},
        {"id": 2, "score": 9.0, "title": "History of Microsoft Corp", "location": "https://en.wikipedia.org/wiki/Microsoft_history"},
        {"id": 3, "score": 8.5, "title": "Bill Gates Biography", "location": "https://example.com/gates"},
        {"id": 4, "score": 8.0, "title": "Paul Allen Biography", "location": "https://example.org/allen"},
    ]
    result = diversify_results(docs, lambda_param=0.5)
    # Highest-scored document is always first.
    assert result[0]["id"] == 1
    result_ids = [d["id"] for d in result]
    assert set(result_ids) == {1, 2, 3, 4}  # nothing dropped
    # The near-duplicate (same host, similar title) should be pushed
    # later than at least one of the more-distinct lower-scored docs.
    assert result_ids.index(2) > 1

    # lambda=1.0 (pure relevance) reduces to original score order.
    pure_relevance = diversify_results(docs, lambda_param=1.0)
    assert [d["id"] for d in pure_relevance] == [1, 2, 3, 4]

    # max_results caps the MMR re-ordering pass but doesn't drop docs.
    capped = diversify_results(docs, lambda_param=0.5, max_results=2)
    assert len(capped) == 4
    assert capped[0]["id"] == 1


if __name__ == "__main__":
    _self_test()
    print("diversity self-test passed.")


__all__ = [
    "DEFAULT_LAMBDA", "SAME_HOST_PENALTY", "jaccard_similarity",
    "document_similarity", "diversify_results",
]



