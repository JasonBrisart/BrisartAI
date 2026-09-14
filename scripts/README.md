# scripts/

Diagnostic replay tools for validating **ranking quality** — distinct from the automated test suite in `brisart_ai/*/tests/` (see [`docs/TESTING.md`](../docs/TESTING.md)), which covers *correctness*. These scripts cover *ranking judgment calls* with a full, inspectable per-component score breakdown.

```text
scripts/
├── debug_offline_replay.py   Offline ranking regression fixtures, no network
└── debug_search_replay.py    Live provider replay against real web search
```

---

## `debug_offline_replay.py`

Builds a temporary SQLite index from in-file text fixtures and runs the real `brisart_ai.knowledge.ranker.search()` against it — no network involved. This exists specifically because `debug_search_replay.py` depends on whatever the live providers feel like returning at that moment; a provider under rate-limiting can return well-formed HTML for an unrelated query, making a real ranking bug hard to distinguish from a bad day for the search provider. Four fixtures ship by default (microsoft/founder, transistor/inventor, cats/statistic, purr/explanation), each asserting a specific expected top result.

```bash
python scripts/debug_offline_replay.py            # all fixtures
python scripts/debug_offline_replay.py microsoft   # one fixture by name
python scripts/debug_offline_replay.py --list      # list names/queries only
```

Exit status is non-zero when any fixture's expected top result doesn't win. The fixture database is built in a temp directory and deleted on exit; nothing is written to the repository.

---

## `debug_search_replay.py`

Replays the real web search path against **live** providers and shows why results survived: which query forms were sent (natural phrasing vs. keyword fallback), which provider actually answered, which batches were rejected wholesale as unrelated, and the full per-URL scoring breakdown (base score, intent delta, terms matched, whether a phrase match fired) for the final ranking.

```bash
python scripts/debug_search_replay.py                          # default 10-query regression set
python scripts/debug_search_replay.py --query "who founded x"  # one specific query
python scripts/debug_search_replay.py --limit 5 --delay 45     # results-per-query, seconds between queries
```

Defaults to a 45-second delay between queries because live providers rate-limit aggressively — lower it only for a single-query run. `KeyboardInterrupt` returns exit code 130 rather than a traceback.
