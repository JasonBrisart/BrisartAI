# BrisartAI

**Local research intelligence. Pure Python. Local-first. Dependency-free.**

BrisartAI is a desktop research assistant that turns local files, notes, code, and — when you allow it — public web material into a **searchable, source-grounded knowledge system**. It finds the evidence you already have, ranks it, and quotes it back with citations. It does not invent facts, and it does not phone home.

Built for researchers, developers, archivists, and labs that want inspectable research infrastructure with **no hosted backend, no proprietary AI API, no telemetry, and no third-party package chain**. It runs on ordinary workstations and in offline / air-gapped environments.

---

## At a glance

| | |
|---|---|
| **Run it** | `python run.py` |
| **Interface** | Local Tkinter desktop app (GUI-only) |
| **Storage** | Local SQLite |
| **Runtime dependencies** | Python standard library only |
| **Network** | Optional; fully disableable for air-gapped use |
| **Author** | Jason Brisart — Brisart research tooling ecosystem |

## What it does

- **Indexes local material** — notes, Markdown/text, source code, structured data, and Office/PDF documents — into a local SQLite store.
- **Answers from evidence** — retrieves the best passages and quotes them back with sources. When the evidence is thin, it says so.
- **Searches the public web (optional)** — only when you enable it; otherwise everything works locally with zero outbound requests.
- **Ranks with the Brisart Relevance Engine** — a custom, inspectable, non-TF-IDF/BM25 pipeline that ranks a source because it's likely to *answer the question*, not just repeat its words.

---

## Quick start

Requires a Python 3 install with Tkinter and write access in the working folder. No third-party packages needed.

```bash
python run.py        # or, on Windows: py run.py  /  start.bat
```

`run.py` opens the desktop app. Any startup failure (locked index, read-only folder) is caught and shown as a dialog, not a raw traceback.

Then: add local material through the interface, let it index, and ask a question. Enable public web research only when appropriate for your environment. For air-gapped use, leave web research off and index only approved local material.

---

## How it works

```text
Local files + (optional) web pages
        │  extract & clean            (io/)
        ▼
Local SQLite index                    (knowledge/index.py)
        │  Brisart Relevance Engine   (knowledge/relevance_engine.py + ranker.py + intent.py)
        ▼
Evidence selection & synthesis        (knowledge/synthesizer.py)
        ▼
Source-grounded desktop UI            (ui/)
```

Full request flow, storage schema, the ranking pipeline, and a "where do I change X?" map live in **[`ARCHITECTURE.md`](ARCHITECTURE.md)**.

BrisartAI also ships the **Brisart Native Stack** — pure-Python, from-spec reimplementations of the stdlib primitives it relies on (SHA-256, Base64, DEFLATE, URL/JSON/HTML parsing, robots.txt), each verified against the stdlib and wired into production. Details and verification: **[`brisart_ai/native/README.md`](brisart_ai/native/README.md)**.

---

## Repository layout

```text
BrisartAI/
├── brisart_ai/
│   ├── core/        Conversation routing, session memory, settings
│   ├── io/          Readers, extraction, input cleaning
│   ├── knowledge/   Indexing, ranking, relevance, synthesis, vault
│   ├── native/      The Brisart Native Stack
│   ├── ui/          Tkinter interface + service boundary
│   ├── web/         Optional public web research
│   ├── blocklist.py / intent.py / util.py / version_info.py   Shared layer
│   └── tests/       Tests for the shared modules (each package has its own tests/)
├── data/            Local configuration (research_settings.json)
├── docs/            Durable project documentation (see below)
├── scripts/         Diagnostic ranking-replay utilities
├── run.py           Application launcher
└── version.py       Canonical release version
```

Each source package carries its own `README.md`; file-level docstrings own each module's contract, parameters, relationships, and edge cases.

---

## Documentation

| Document | Owns |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System design, request flow, storage model, "where do I change X?" |
| [`TESTING.md`](TESTING.md) | Test layout, commands, scope |
| [`SECURITY.md`](SECURITY.md) | Private vulnerability reporting, security scope, air-gapped policy |
| [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) | Open and resolved issues (standardized bug-report format) |
| [`CHANGELOG.md`](CHANGELOG.md) | Full release history |
| [`brisart_ai/native/README.md`](brisart_ai/native/README.md) | The Brisart Native Stack and its verification |

Each fact has exactly one authoritative home — this README points to it rather than duplicating it. Security details are in `SECURITY.md`; the honest limitations list is in `KNOWN_ISSUES.md`; supported file types are documented in [`brisart_ai/io/README.md`](brisart_ai/io/README.md).
