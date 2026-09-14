# Documentation Index

This folder holds BrisartAI's **durable** documentation — the things that need a stable home and shouldn't drift into the code.

Two kinds of documentation live elsewhere and are deliberately *not* duplicated here:

- **Project orientation** (what BrisartAI is, how to run it, capabilities, layout) lives in the root [`README.md`](../README.md).
- **Per-package technical references** live as a `README.md` inside each `brisart_ai/` subfolder, beside the code they describe.

## What's in this folder

| Document | What it's for |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Macro-to-micro system design: layer responsibilities, request flow, storage schema, the ranking pipeline, and a "where do I make a change?" map. |
| [`SECURITY.md`](SECURITY.md) | How to privately report a vulnerability, response expectations, security scope, and the air-gapped / local-data operating policy. |
| [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) | Every open, non-trivial issue in a standardized bug-report format, plus a durable log of resolved issues. |
| [`TESTING.md`](TESTING.md) | Test-suite layout, how to run it, why `pytest` is the runner, and what's deliberately out of scope. |
| [`CHANGELOG.md`](CHANGELOG.md) | Full release history, newest first. |

## Where to start

If you're new to the project, read the root [`README.md`](../README.md) first, then [`ARCHITECTURE.md`](ARCHITECTURE.md). From there, open the `README.md` inside whichever `brisart_ai/` package you need to work in, and finally the top-of-file docstring of the specific module you're changing.

## Documentation ownership

To prevent drift, each fact has exactly one authoritative home:

- **Root `README.md`** — orientation, capabilities, setup, repository layout.
- **`docs/ARCHITECTURE.md`** — detailed design and change-location guidance.
- **`docs/TESTING.md`** — test policy and authoritative commands.
- **`docs/SECURITY.md`** — vulnerability reporting and security policy.
- **`docs/KNOWN_ISSUES.md`** — open and resolved issue records.
- **`docs/CHANGELOG.md`** — release history.
- **Package `README.md`** — module responsibilities and boundaries.
- **File docstrings** — implementation contracts, parameters, relationships, edge cases.

A summary may appear in more than one place. The *authoritative* version appears in only one.
