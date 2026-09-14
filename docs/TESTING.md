# Testing BrisartAI

Tests are **co-located** with the source they exercise: every folder under `brisart_ai/` that contains source modules also contains its own `tests/` subfolder, right next to the code. There is no separate top-level `tests/` tree to keep in sync with the source layout.

The tests are **pure `unittest.TestCase` classes with zero external test dependencies.** `pytest` is used only as the *runner* — see [Why `pytest`](#why-pytest-and---import-modeimportlib) below for the one reason it's needed.

---

## Layout

```text
brisart_ai/
├── native/tests/        native modules vs. the real stdlib
├── tests/               util.py, blocklist.py, intent.py, version_info.py
├── io/tests/            all io/ modules
├── core/tests/          all core/ modules
├── knowledge/tests/     all knowledge/ modules
├── web/tests/           all web/ modules (network-independent logic only)
└── ui/tests/            theme.py + service.py (headless-safe subset)
```

---

## Running the tests

From the project root, with no flags needed (`pytest.ini` sets `--import-mode=importlib` automatically):

```bash
pytest
```

Run just one folder:

```bash
pytest brisart_ai/native/tests/
pytest brisart_ai/knowledge/tests/test_ranker.py
```

Verbose output:

```bash
pytest -v
```

Individual files also work with plain `unittest` (a *direct*, non-discovery invocation has no recursive package requirement):

```bash
python -m unittest brisart_ai.native.tests.test_brisart_hash
```

---

## Why `pytest`, and why `--import-mode=importlib`

`unittest`'s built-in recursive discovery requires every intermediate directory to have an `__init__.py` to be walked into as a package. `brisart_ai/`'s subfolders are deliberately **namespace packages with no `__init__.py`** (see `brisart_ai/version_info.py`'s docstring for why), so `unittest discover` run from the project root silently finds **zero** tests.

`pytest` has no such restriction and discovers test files by path. The one wrinkle: several `tests/` subfolders share the exact same folder name across different parents (`brisart_ai/native/tests/`, `brisart_ai/web/tests/`, …). `pytest`'s *default* "prepend" import mode would resolve each to the same top-level module name and collide. `--import-mode=importlib` (configured once in `pytest.ini`) resolves each test file by its literal filesystem path instead, so identically-named `tests/` folders never collide. This is `pytest`'s own recommendation for exactly this project shape.

---

## What's covered, and what's deliberately out of scope

- **`brisart_ai/native/`** — every module is tested against the *real* stdlib function it replaces (`hashlib.sha256`, `base64`, `zlib`, `urllib.parse`, `json`, `html.parser`, `urllib.robotparser`), not just internally self-consistent.
- **`brisart_ai/web/search.py` and `crawler.py`** — all pure-logic helpers (URL decoding/unwrapping, tracking-parameter stripping, query cleaning, scoring, ranking, partitioning) are tested directly. The actual HTTP-calling provider functions are **not** exercised — hitting live search engines from a test suite would be flaky and could itself trigger the rate-limiting/challenge-page behavior those functions exist to detect. `fetch_url()` is tested only for its error-handling paths using a non-routable address (`198.51.100.1`, reserved by RFC 5737) so no real network dependency is required.
- **`brisart_ai/ui/`** — `theme.py` (pure constants, no Tk import) and `service.py` (a pure backend facade with no Tk dependency) are fully tested headlessly. `app.py`, `chat_panel.py`, `dialogs.py`, and `sidebar.py` construct real Tkinter widgets and require a live display; they are verified by manually running the application.
- Every test that touches SQLite (`Index`, `SessionMemory`, vault functions, `BrisartService`) uses a fresh `tempfile.TemporaryDirectory()` per test, so tests never share state through the filesystem and can run in any order.

---

## A note on `ResearchSettings()`'s default path

`core/settings.py`'s `ResearchSettings()` defaults to a fixed relative path (`data/research_settings.json`) when no explicit `path=` is given — the correct production behavior, but it means any two default-constructed instances share state through that one file. Every test needing isolated settings either passes an explicit `path=` into its own `tempfile.TemporaryDirectory()`, or (for `BrisartService`, which always constructs `ResearchSettings()` with no override) explicitly resets the toggles it depends on at the start of the test. See `brisart_ai/ui/tests/test_service_headless.py`'s `_make()` helper for the concrete pattern.

---

## Ranking-quality validation (separate from the unit suite)

The unit suite covers *correctness*. Ranking *judgment* — "did the right source win?" — is validated with the replay scripts in `scripts/`, which exercise the real retrieval path with a full per-component score breakdown:

```bash
python scripts/debug_offline_replay.py     # offline ranking fixtures, no network
python scripts/debug_search_replay.py       # live provider replay
```

See [`scripts/README.md`](../scripts/README.md) for details.
