# Testing BrisartAI

Tests are **co-located** with the source they test: every folder under `brisart_ai/` that contains source modules also contains its own `tests/` subfolder, right next to the code it exercises. There is no separate top-level `tests/` tree to keep in sync with the source layout.

**379 tests total, zero external dependencies for the tests themselves** (pure `unittest.TestCase` classes). `pytest` is used only as the *runner*, because it can discover same-named `tests/` folders scattered across the tree without requiring `__init__.py` files — which would conflict with this project's deliberate "no `__init__.py` anywhere in `brisart_ai/`" design (see `brisart_ai/version_info.py`'s own docstring for why).

## Layout

```
brisart_ai/
├── native/tests/        78 tests  -- all 7 native modules vs. real stdlib
├── tests/                65 tests  -- util.py, blocklist.py, intent.py, version_info.py
├── io/tests/              49 tests  -- all 4 io/ modules
├── core/tests/            22 tests  -- all 3 core/ modules
├── knowledge/tests/       80 tests  -- all 6 knowledge/ modules
├── web/tests/             69 tests  -- all 6 web/ modules
└── ui/tests/              16 tests  -- theme.py + service.py (headless-safe subset)
                          -----
                          379 tests total
```

## Running the tests

From the project root, with no flags needed (`pytest.ini` sets the required `--import-mode=importlib` automatically):

```bash
pytest
```

Run just one folder's tests:

```bash
pytest brisart_ai/native/tests/
pytest brisart_ai/knowledge/tests/test_ranker.py
```

Verbose output:

```bash
pytest -v
```

### Why pytest, and why `--import-mode=importlib`

`unittest discover`'s built-in recursive discovery requires every intermediate directory to have an `__init__.py` to be walked into as a package. Since `brisart_ai/`'s subfolders are deliberately namespace packages with **no** `__init__.py`, `unittest discover` run from the project root silently finds **zero** tests.

`pytest` doesn't have that restriction and discovers test files by path directly. The one wrinkle: several `tests/` subfolders share the exact same folder name across different parents (`brisart_ai/native/tests/`, `brisart_ai/web/tests/`, etc.), and pytest's *default* "prepend" import mode resolves a test module's dotted name by walking up to the first `__init__.py`-less ancestor — which is immediately, for all of them — causing every same-named `tests` folder to collide on the same top-level module name. `--import-mode=importlib` (configured once in `pytest.ini`) resolves each test file by its literal filesystem path instead, so identically-named `tests/` folders never collide. This is pytest's own recommendation for exactly this project shape.

Individual test files still work fine with plain `unittest` too — `python3 -m unittest brisart_ai.native.tests.test_brisart_hash` run from the project root works, since a direct (non-discovery) unittest invocation doesn't have the recursive `__init__.py` requirement.

## What's covered, and what's deliberately out of scope

- **`brisart_ai/native/`** — every module is tested against the *real* stdlib function it replaces (`hashlib.sha256`, `base64`, `zlib`, `urllib.parse`, `json`, `html.parser`, `urllib.robotparser`), not just internally self-consistent.
- **`brisart_ai/web/search.py` and `crawler.py`** — all pure-logic helpers (URL decoding/unwrapping, tracking-parameter stripping, query cleaning, scoring, ranking, partitioning) are tested directly. The actual HTTP-calling provider functions are **not** exercised, since hitting live search engines from a test suite would be flaky and could itself trigger the rate-limiting/challenge-page behavior those functions exist to detect. `fetch_url()` is tested only for its error-handling paths using a non-routable address (`198.51.100.1`, reserved by RFC 5737) so no real network dependency is required.
- **`brisart_ai/ui/`** — `theme.py` (pure constants, no Tk import) and `service.py` (a pure backend facade with no Tk dependency) are fully tested headlessly. `app.py`, `chat_panel.py`, `dialogs.py`, and `sidebar.py` all construct real `tkinter` widgets and require a live display; they are verified by manually running the application instead.
- Every test that touches SQLite (`Index`, `SessionMemory`, vault functions, `BrisartService`) uses a fresh `tempfile.TemporaryDirectory()` per test, so tests never share state through the filesystem and can run in any order.

## A note on `ResearchSettings()`'s default path

`brisart_ai/core/settings.py`'s `ResearchSettings()` defaults to a fixed relative path (`data/research_settings.json`) when no explicit `path=` is given — the correct, intended production behavior, but it means any two test instances relying on the default constructor share state through that one file. Every test that needs isolated settings either passes an explicit `path=` into its own `tempfile.TemporaryDirectory()`, or (for `BrisartService`, which always constructs `ResearchSettings()` with no override) explicitly resets the toggles it depends on at the start of the test. See `brisart_ai/ui/tests/test_service_headless.py`'s `_make()` helper for the concrete pattern.
