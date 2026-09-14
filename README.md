# BrisartAI

**Local research intelligence. Pure Python. Local-first. Dependency-free.**

BrisartAI is a desktop research assistant that turns local files, notes, source code, documentation, and — when you allow it — public web material into a **searchable, source-grounded knowledge system**. It finds the evidence you already have, ranks it, and quotes it back to you with citations. It does not invent facts, and it does not phone home.

It is built for researchers, developers, archivists, independent investigators, and laboratories that want inspectable research infrastructure with **no hosted backend, no proprietary AI API, no telemetry, and no third-party package chain**.

---

## At a glance

| | |
|---|---|
| **Release** | 1.0.0 |
| **Entry point** | `python run.py` |
| **Interface** | Local Tkinter desktop application (GUI-only) |
| **Storage** | Local SQLite |
| **Runtime dependencies** | Python standard library only |
| **Network** | Optional; fully disableable for air-gapped use |
| **Author** | Jason Brisart — part of the Brisart research tooling ecosystem |

BrisartAI runs on ordinary workstations, controlled institutional systems, and offline or air-gapped research environments.

---

## Why BrisartAI exists

Most research tools reach for cloud infrastructure, hosted models, external APIs, vector databases, background telemetry, and deep dependency trees. BrisartAI takes the opposite position on every one of those choices:

- **Your data stays yours.** Nothing local is uploaded. There is no server.
- **The reasoning is inspectable.** Ranking is a documented, deterministic pipeline — not an opaque model.
- **Answers are grounded.** Every answer traces back to indexed source material.
- **It is understandable end to end.** Pure Python, from the entry point down to the hashing and URL-parsing primitives.
- **Boundaries are documented from macro to micro** — repository, package, and individual file.
- **The network is optional and isolated.** The offline research path never depends on it.

The goal is not to imitate a hosted general-purpose assistant. It is to be a maintainable local research system whose evidence, storage, ranking, and behavior can be examined directly by the people who rely on it.

---

## Core capabilities

### Local research collections
Ingest supported material into a local SQLite knowledge index — research notes, Markdown and plain-text docs, source code, structured data (JSON, CSV, YAML, TOML, INI), Office and research documents, HTML/XML, and preservation-oriented records.

### Source-grounded answers
BrisartAI retrieves evidence from the index and synthesizes an answer from the passages it actually finds, preserving attribution so you can trace any answer back to its source. When the evidence is thin, it says so rather than dressing up a guess as a citation.

### Optional public web research
When enabled, the web subsystem searches public providers, evaluates candidate results, applies crawl policy, fetches useful pages, extracts readable content, and folds selected material into the local workflow. When disabled, everything above continues to work against local data with **zero outbound requests**.

### The Brisart Relevance Engine
A custom, non-TF-IDF/BM25 retrieval engine built specifically for this project's corpus shape. It weighs term rarity, query coverage, document focus and length, title relevance, verbatim phrase matches, term proximity, and question intent — with one governing principle:

> Rank a source because it is likely to *answer the question*, not merely because it repeats some of the same words.

---

## Architecture at a glance

```text
Local files  +  (optional) public web pages
                     │
                     ▼
          Extraction and cleaning              (io/)
                     │
                     ▼
          Local SQLite knowledge index         (knowledge/index.py)
                     │
                     ▼
          Brisart Relevance Engine             (knowledge/relevance_engine.py + ranker.py + intent.py)
                     │
                     ▼
          Evidence selection and synthesis     (knowledge/synthesizer.py)
                     │
                     ▼
          Source-grounded desktop UI           (ui/)
```

The major areas:

- **`brisart_ai/core/`** — conversation routing, session memory, settings
- **`brisart_ai/io/`** — file reading, binary-document handling, extraction, input cleaning
- **`brisart_ai/knowledge/`** — ingestion, indexing, ranking, relevance, synthesis, vault
- **`brisart_ai/native/`** — the Brisart Native Stack: pure-Python standard-library replacements
- **`brisart_ai/ui/`** — the Tkinter application and its service boundary
- **`brisart_ai/web/`** — optional search, fetching, crawl policy, models, statistics
- **`brisart_ai/{util,intent,blocklist}.py`** — shared tokenization/hashing/URL helpers, query-intent classification, junk-host policy

Dependencies point **inward and downward**: `web/` and `knowledge/` may use the shared layer; the shared layer depends on nothing above it; `native/` sits at the very bottom and knows nothing about BrisartAI's domain at all. Full request flow, storage schema, and a "where do I change X?" map live in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## The Brisart Native Stack

BrisartAI carries pure-Python, from-spec reimplementations of the standard-library primitives it depends on, each **verified against the real stdlib function it replaces** and wired into its production call sites:

| Module | Replaces | Standard it implements |
|---|---|---|
| `brisart_hash` | `hashlib.sha256` | SHA-256 (FIPS 180-4) |
| `brisart_codec` | `base64` | Base64 (RFC 4648) |
| `brisart_inflate` | `zlib.decompress` | DEFLATE + zlib (RFC 1951 / 1950) |
| `brisart_url` | `urllib.parse` | URL syntax (RFC 3986) |
| `brisart_json` | `json` | JSON (RFC 8259) |
| `brisart_markup` | `html.parser.HTMLParser` | Lenient HTML tokenizing |
| `brisart_robots` | `urllib.robotparser` | Robots Exclusion Protocol |

Actual HTTP transport stays with Python's own networking; ZIP and XML handling remain standard-library responsibilities. The native stack replaces *parsing and encoding logic*, not the network. Verification results, deliberate differences, and integration points are documented in [`brisart_ai/native/README.md`](brisart_ai/native/README.md).

---

## Requirements

- A supported Python 3 installation
- Tkinter available in that Python (for the desktop interface)
- Write access in the working location (for local settings and SQLite data)
- Network access **only** if public web research is enabled

No third-party Python packages are required to run the application.

---

## Quick start

From the repository root:

```bash
python run.py
```

On Windows, either works:

```bat
py run.py
start.bat
```

`run.py` imports the application entry point from `brisart_ai.ui.app` and opens the desktop interface. Any startup failure (a locked index file, a read-only install folder) is caught in exactly one place and surfaced as a friendly dialog rather than a raw traceback.

---

## Basic workflow

1. Launch BrisartAI from the repository root.
2. Add or select local research material through the interface.
3. Let it extract and index the material locally.
4. Ask a research question.
5. Read the answer and follow its cited sources.
6. Enable public web research only when external retrieval is appropriate for your environment.

For controlled or air-gapped deployments, leave web research disabled and populate the index only with approved local material.

---

## Supported file types

**Text, markup, structured data** — plain text, Markdown, HTML/XML, CSV/TSV, JSON/JSON Lines, YAML/TOML, INI/config, logs.
**Source code** — Python, JavaScript/TypeScript, Java, C/C++, C#, Go, Rust, shell/PowerShell, SQL, and other text-based formats recognized by the reader configuration.
**Document containers** — PDF, DOCX, PPTX, XLSX, ODT.

Binary-document support depends on the best-effort extraction in `brisart_ai/io/binary_readers.py`. A file whose extension is recognized but which yields no usable text is **not** counted as a successful source.

---

## Repository layout

```text
BrisartAI/
├── .github/               GitHub platform configuration (funding only; no CI)
├── brisart_ai/
│   ├── core/              Conversation routing, session memory, settings
│   ├── io/                Readers, extraction, input cleaning
│   ├── knowledge/         Indexing, ranking, relevance, synthesis, vault
│   ├── native/            The Brisart Native Stack
│   ├── ui/                Tkinter interface + service boundary
│   ├── web/               Optional public web research
│   ├── tests/             Tests for the top-level shared modules
│   ├── blocklist.py       Shared junk-host / function-word policy
│   ├── intent.py          Query- and answer-intent classification
│   ├── util.py            Shared utilities
│   └── version_info.py    Runtime version loading
├── data/                  Local configuration data
├── docs/                  Durable project documentation
├── scripts/               Diagnostic replay utilities
├── README.md              This file
├── run.py                 Application launcher
├── start.bat              Windows launcher
└── version.py             Canonical release version
```

Each major source folder carries its own `README.md` describing that package's role, file responsibilities, boundaries, and maintenance notes.

---

## Documentation

The root README is the front door. Everything deeper lives in one clearly named place:

| Document | Owns |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design, request flow, storage model, "where do I change X?" |
| [`docs/TESTING.md`](docs/TESTING.md) | Test layout, commands, scope, deliberate exclusions |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Private vulnerability reporting, security scope, air-gapped policy |
| [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) | Open and resolved issues in a standardized bug-report format |
| [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | Full release history |
| [`brisart_ai/native/README.md`](brisart_ai/native/README.md) | The Brisart Native Stack and its verification |

Per-package `README.md` files stay beside the code they describe. File-level docstrings own each module's contract, parameters, relationships, and edge cases. The same detailed explanation is never duplicated across documents — a summary may appear in more than one place, but the authoritative version lives in exactly one.

---

## Security model

Local-first does not automatically mean secure. Operators remain responsible for host OS security, file permissions, physical access, backups, approval of indexed material, network policy when web research is on, and review of anything exported. Report vulnerabilities privately per [`docs/SECURITY.md`](docs/SECURITY.md) rather than in a public issue.

---

## Known limitations

- Retrieval cannot rank a source that was never discovered or indexed.
- Public search providers can change markup, block automated requests, or return incomplete results.
- Some ranking and intent vocabularies are intentionally finite and grow as real gaps are found.
- Live web-provider behavior cannot be fully represented by offline tests.
- Tkinter behavior depends on a working graphical environment.
- ZIP and XML document handling still rely on the Python standard library, not Brisart Native Stack replacements.

The authoritative, reproducible issue list — with severity, affected components, what was ruled out, and next steps — lives in [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md).

---

## Licensing

BrisartAI is released under the **Brisart Ecosystem License**. Official releases are free for operational use. Rights to modify, fork, or commercialize require an active subscription (single-seat and research-lab tiers are available). See the repository's license terms for the authoritative details.

---

## Author

Created and maintained by **Jason Brisart** as part of the Brisart research tooling ecosystem.

---

## Final note

BrisartAI is built around one principle: **research infrastructure should stay understandable to the people who depend on it.** Local storage, inspectable ranking, source-grounded answers, explicit architecture, package-level documentation, and a pure-Python implementation all exist to serve that.
