# brisart_ai/native/ — The Brisart Native Stack

Pure-Python, from-spec reimplementations of the standard-library building blocks BrisartAI relies on, so the project's own philosophy ("no external dependencies, fully inspectable, custom where it earns you something") extends past `brisart_ai/` itself and into the primitives it's built on.

Every module below is **independently verified byte-for-byte / decision-for-decision against the real stdlib function it replaces**, not just internally self-consistent, and every module is **wired into its real call sites** across the rest of the application.

## What's here, what it replaces, and where it's used

| Module | Replaces | Verified against real stdlib | Wired into |
|---|---|---|---|
| `brisart_hash.py` — **BrisartHash256** | `hashlib.sha256()` | Exact hex-digest matches across every 64-byte block-boundary edge case and streaming `update()` | `util.py` (`stable_hash`, `file_hash`) |
| `brisart_codec.py` — **BrisartBase64** | `base64.b64encode/b64decode/urlsafe_b64decode` | Exact matches, including the missing-padding case Bing's redirect wrapper actually produces | `web/search.py` (Bing redirect unwrap) |
| `brisart_inflate.py` — **BrisartInflate** | `zlib.decompress()` + Adler-32 | Exact matches: empty input, dynamic and fixed Huffman blocks, overlapping LZ77 back-references, pure random (incompressible) data | `io/binary_readers.py` (PDF stream decompression) |
| `brisart_url.py` — **BrisartURL** | `urllib.parse` (split/unsplit/quote/unquote/urlencode/parse_qsl/urljoin) | Exact matches, including RFC 3986 dot-segment resolution and IPv6-literal hostnames | `util.py`, `blocklist.py`, `intent.py`, `io/extractor.py`, `web/policy.py`, `web/search.py`, `web/crawler.py` |
| `brisart_json.py` — **BrisartJSON** | `json.loads/dumps` | Exact matches; one documented, deliberate non-bug difference (see below) | `core/settings.py`, `io/readers.py`, `web/search.py` |
| `brisart_markup.py` — **BrisartMarkupParser** | `html.parser.HTMLParser` (as a base class) | Exact event-sequence matches, including a real behavioral bug this process caught and fixed (see below) | `io/extractor.py`, `web/search.py` |
| `brisart_robots.py` — **BrisartRobotsPolicy** | `urllib.robotparser.RobotFileParser` | Exact `can_fetch()` decisions, after a rewrite to match the stdlib's own algorithm rather than a newer one (see below) | `web/policy.py` |

Actual HTTP networking (`urllib.request`/`urllib.error`) is unchanged at every call site above — the native stack replaces parsing and encoding logic, not the network transport itself.

## Two real bugs this process caught (worth knowing about)

**`BrisartMarkupParser` — void-element handling.** An early draft assumed `handle_startendtag()` fires automatically for "void" elements (`<br>`, `<img>`, `<input>`) even without an explicit trailing `/`. Verified directly against `html.parser.HTMLParser`: it only fires `handle_startendtag()` when the source markup *itself* writes `<br/>`; a bare `<br>` fires ordinary `handle_starttag()`. Fixed and re-verified.

**`BrisartRobotsPolicy` — matching algorithm.** An early draft implemented the modern RFC 9309 algorithm (longest-match-wins, `*` wildcards, `$` end-anchors) — the algorithm most current crawlers actually use. Verified against `urllib.robotparser.RobotFileParser` and it disagreed on several test decisions. Reading the stdlib's actual source showed why: Python's `robotparser` implements the older, simpler 1994 protocol — literal prefix matching only, and first-matching-rule-in-file-order wins, not most-specific-match. Since the goal was a faithful drop-in replacement for *this specific class*, the module was rewritten to mirror the stdlib's actual algorithm, including its quirks (a ruleless group before a blank line is silently discarded; a group mixing `"*"` with a named agent is treated purely as the default group).

## The one documented non-bug difference

`BrisartJSON`'s pretty-printer emits non-ASCII characters as raw UTF-8 (`"café"`) rather than `json.dumps()`'s default `ensure_ascii=True` behavior (`"caf\u00e9"`). Both are valid JSON per RFC 8259 — this is a deliberate design choice so BrisartAI's own content (a source title copied verbatim from a crawled page, for instance) round-trips without forced escape sequences. The actual data round-trips correctly through both `json.loads()` and `brisart_loads()` in both directions; only the literal escaping style differs for non-ASCII text.

## What's deliberately not included

- **ZIP container parsing** (`zipfile`, used by `io/binary_readers.py` for `.docx`/`.pptx`/`.xlsx`/`.odt`). A ZIP file's local-file-header and central-directory format is its own real parsing job on top of the DEFLATE decompressor already built here — a distinct, comparably-sized effort.
- **XML parsing** (`xml.etree.ElementTree`, used by the same readers for document content once unzipped). Same reasoning: doable, but its own well-scoped project.

Both are realistic candidates for a follow-up pass, built and verified the same way everything above was.

## Running the self-tests

Every module has an `if __name__ == "__main__":` self-test:

```bash
python3 -m brisart_ai.native.brisart_hash
python3 -m brisart_ai.native.brisart_codec
python3 -m brisart_ai.native.brisart_inflate
python3 -m brisart_ai.native.brisart_url
python3 -m brisart_ai.native.brisart_json
python3 -m brisart_ai.native.brisart_markup
python3 -m brisart_ai.native.brisart_robots
```

These are internal consistency checks. The full stdlib-comparison regression suite lives in `brisart_ai/native/tests/` (78 tests total) — each test module imports the real stdlib function it compares against directly, so `pytest brisart_ai/native/tests/` is the authoritative, re-runnable version of the verification summarized above.
