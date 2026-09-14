# BrisartAI

**Local research intelligence. Pure Python. Local first. Dependency free.**

BrisartAI is a desktop research assistant for turning local files, notes, documentation, source code, research records, and optional public web material into a searchable, source-grounded knowledge system.

It is designed for researchers, developers, archivists, independent investigators, and laboratories that need inspectable research infrastructure without a hosted backend, proprietary AI API, telemetry pipeline, or third-party Python package chain.

## Project Status

- **Release:** 1.0.0
- **Entry point:** `run.py`
- **Primary interface:** Local Tkinter desktop application
- **Storage:** Local SQLite databases
- **Runtime dependencies:** Python standard library only
- **Operating model:** Local-first, with optional public web research
- **Offline use:** Supported when web research is disabled

BrisartAI is suitable for ordinary workstations, controlled institutional systems, and offline or air-gapped research environments.

## Why BrisartAI Exists

Many research tools depend on cloud infrastructure, hosted models, external APIs, vector databases, background telemetry, and large dependency trees. BrisartAI follows a different engineering model:

- Local data remains under the operator's control.
- Retrieval and ranking behavior is inspectable.
- Answers are grounded in indexed sources.
- The application remains understandable without a remote service.
- Core functionality is implemented in pure Python.
- System boundaries are documented from repository level to individual modules.
- Optional network features are isolated from the offline research path.

The goal is not to imitate a hosted general-purpose assistant. The goal is to provide a maintainable local research system whose evidence, storage, ranking, and operational behavior can be examined directly.

## Core Capabilities

### Local research collections

BrisartAI can ingest supported files into a local SQLite knowledge index. Typical inputs include:

- Research notes and archives
- Markdown and plain-text documentation
- Source code and configuration files
- Structured data such as JSON, CSV, YAML, TOML, and INI
- Office and research documents
- HTML and XML content
- Historical or preservation-oriented records

### Source-grounded answers

BrisartAI retrieves evidence from the local index and synthesizes answers from the material it finds. Source attribution is preserved so an operator can trace an answer back to the indexed material.

If the available evidence is insufficient, the system is designed to avoid presenting unsupported material as if it were sourced.

### Optional public web research

When enabled, the web subsystem can search public providers, evaluate candidate results, apply crawl policy, fetch useful pages, extract readable content, and add selected material to the local research workflow.

When disabled, BrisartAI continues to operate against local indexed data without requiring a hosted backend.

### Brisart Relevance Engine

The Brisart Relevance Engine is the project's custom local retrieval and ranking system. It evaluates signals such as:

- Query-term rarity
- Query coverage
- Document focus and shape
- Title relevance
- Phrase matching
- Term proximity
- Question intent

Its objective is straightforward:

> Rank material because it is likely to answer the question, not merely because it contains some of the same words.

## Architecture at a Glance

```text
Local files and optional public web pages
                    |
                    v
          Extraction and cleaning
                    |
                    v
          Local SQLite knowledge index
                    |
                    v
          Brisart Relevance Engine
                    |
                    v
        Evidence selection and synthesis
                    |
                    v
          Source-grounded desktop UI
```

The main architectural areas are:

- `brisart_ai/core/`: conversation state, session memory, and settings
- `brisart_ai/io/`: file reading, binary document handling, extraction, and cleaning
- `brisart_ai/knowledge/`: ingestion, indexing, ranking, relevance, synthesis, and vault operations
- `brisart_ai/native/`: custom pure-Python infrastructure primitives
- `brisart_ai/ui/`: desktop interface and application service layer
- `brisart_ai/web/`: optional search, fetching, crawl policy, result models, and statistics

For request flow, storage responsibilities, change locations, and module relationships, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Brisart Native Stack

BrisartAI includes custom pure-Python implementations of several infrastructure primitives used throughout the application:

- SHA-256 hashing
- Base64 encoding and decoding
- DEFLATE decompression
- URL parsing and composition
- JSON parsing and serialization
- HTML tokenization
- `robots.txt` policy evaluation

These modules are integrated into their production call sites. Actual HTTP transport remains a separate responsibility of Python's networking facilities. ZIP container handling and XML parsing also remain standard-library responsibilities.

The native modules are not presented as mysterious black boxes. Their behavior, integration points, deliberate differences, and test strategy are documented in [`brisart_ai/native/README.md`](brisart_ai/native/README.md).

## Requirements

- A supported Python 3 installation
- Tkinter available in the Python installation for the desktop interface
- Write permission in the working location for local settings and SQLite data
- Network access only if public web research is enabled

No third-party Python packages are required to run the application itself.

## Quick Start

From the repository root:

```bash
python run.py
```

On Windows, either of the following may be used:

```powershell
py run.py
```

```powershell
start.bat
```

The launcher imports the application entry point from `brisart_ai.ui.app` and starts the local desktop interface.

## Basic Workflow

1. Start BrisartAI from the repository root.
2. Add or select local research material through the application interface.
3. Allow the material to be extracted and indexed locally.
4. Ask a research question.
5. Review the answer and its cited sources.
6. Enable public web research only when external retrieval is appropriate for the environment.

For controlled or air-gapped deployments, leave web research disabled and populate the knowledge index only with approved local material.

## Supported File Types

BrisartAI's ingestion layer is organized around readable text, structured data, source code, markup, and selected document containers. Supported categories include:

### Text, markup, and structured data

- Plain text and Markdown
- HTML and XML
- CSV and TSV
- JSON and JSON Lines
- YAML and TOML
- INI and configuration files
- Logs and other readable text formats

### Source code

- Python
- JavaScript and TypeScript
- Java
- C and C++
- C#
- Go
- Rust
- Shell and PowerShell scripts
- SQL
- Additional text-based programming formats recognized by the reader configuration

### Document containers

- PDF
- DOCX
- PPTX
- XLSX
- ODT

Binary document support depends on the extraction capabilities implemented in `brisart_ai/io/binary_readers.py`. Files that cannot yield usable text are not treated as successful research sources merely because their extension is recognized.

## Repository Layout

```text
BrisartAI/
|-- .github/                 GitHub platform configuration
|-- brisart_ai/
|   |-- core/                Conversation, memory, and settings
|   |-- io/                  Readers, extraction, and input cleaning
|   |-- knowledge/           Indexing, ranking, synthesis, and vault
|   |-- native/              Brisart Native Stack
|   |-- ui/                  Tkinter interface and service boundary
|   |-- web/                 Optional public web research
|   |-- tests/               Tests for top-level shared modules
|   |-- blocklist.py         Shared vocabulary and filtering data
|   |-- intent.py            Query and answer-intent classification
|   |-- util.py              Shared utility functions
|   `-- version_info.py      Runtime version loading
|-- data/                    Local configuration data
|-- docs/                    Durable project documentation
|-- scripts/                 Diagnostic and replay utilities
|-- README.md                Project entry documentation
|-- run.py                   Application launcher
|-- start.bat                Windows launcher
`-- version.py               Canonical release version
```

Each major source folder contains its own `README.md` describing that package's exact role, file responsibilities, communication boundaries, settings, and maintenance considerations.

## Documentation

The root README is the primary orientation document. Detailed records remain separate when they have a durable operational purpose:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): Full system design, request flow, storage model, boundaries, and maintenance map
- [`docs/TESTING.md`](docs/TESTING.md): Test organization, commands, scope, and deliberate exclusions
- [`docs/SECURITY.md`](docs/SECURITY.md): Private vulnerability reporting, security scope, and local-data operating expectations
- [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md): Current limitations and resolved issue history in a standardized bug-report format
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md): Release history and verification notes

Per-package references remain beside the code they describe. This keeps implementation-specific documentation close to the modules most likely to change with it.

## Testing

The test suite is co-located with the source areas it validates. Test folders exist beneath the relevant application packages, including the native, I/O, core, knowledge, web, UI-service, and top-level shared-module areas.

From the repository root, run:

```bash
python -m pytest
```

The application has no third-party runtime dependencies. If `pytest` is used as the test discovery runner, it is a development-time testing tool rather than an application runtime dependency.

Tests cover deterministic behavior such as parsing, indexing, ranking, synthesis, settings, utility functions, native primitives, and network-independent web logic. Real Tkinter widget construction and live provider behavior require environment-appropriate validation beyond purely headless unit tests.

See [`docs/TESTING.md`](docs/TESTING.md) for the authoritative testing policy and commands.

## Local Data and Generated Files

BrisartAI creates local runtime data, including SQLite database files and their temporary journal companions. These files are intentionally excluded from version control.

Common generated files include:

- `brisart_ai_index.sqlite3`
- `brisart_ai_index.sqlite3-shm`
- `brisart_ai_index.sqlite3-wal`
- Session or conversation memory databases
- Local caches, exports, logs, and machine-specific settings

Do not commit generated databases, local secrets, machine-specific settings, or research collections unless they have been deliberately reviewed and approved for publication.

## Security Model

BrisartAI is local-first, but local operation does not automatically make every deployment secure. Operators remain responsible for:

- Host operating-system security
- File and directory permissions
- Physical access controls
- Backup protection
- Approval of indexed research material
- Network policy when web research is enabled
- Review of exported or shared data

Security vulnerabilities should be reported privately according to [`docs/SECURITY.md`](docs/SECURITY.md). Do not publish exploit details before a coordinated fix or mitigation is available.

## Known Limitations

Important current limitations include:

- Retrieval cannot rank a source that was never discovered or indexed.
- Public search providers may change markup, block automated requests, or return incomplete result sets.
- Some ranking and intent vocabularies are intentionally finite and maintained as observed gaps are found.
- Live web-provider behavior cannot be completely represented by offline tests.
- Tkinter widget behavior depends on a working graphical environment.
- ZIP and XML document handling still relies on Python standard-library components rather than Brisart Native Stack replacements.

The authoritative issue list, reproduction details, severity, affected components, attempted mitigations, and next steps are maintained in [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md).

## Maintenance Guidance

Before changing behavior:

1. Identify the owning package in the architecture document.
2. Read that package's local `README.md`.
3. Read the target file's top-of-file documentation.
4. Check `docs/KNOWN_ISSUES.md` for related constraints or prior decisions.
5. Add or update tests beside the affected package.
6. Run the focused test folder.
7. Run the complete test suite.
8. Update the changelog when the change is release-relevant.
9. Recheck documentation for stale architecture, command, version, or limitation statements.

Changes should preserve the project's local-first behavior, explicit module boundaries, source traceability, and dependency-free runtime unless a future release deliberately changes those principles.

## Documentation Maintenance Policy

To prevent drift and duplication:

- The root `README.md` owns project orientation, capabilities, setup, repository layout, and links to deeper material.
- `docs/ARCHITECTURE.md` owns detailed system design and change-location guidance.
- `docs/TESTING.md` owns test policy and authoritative test commands.
- `docs/SECURITY.md` owns vulnerability reporting and security policy.
- `docs/KNOWN_ISSUES.md` owns open and resolved issue records.
- `docs/CHANGELOG.md` owns historical release records.
- Package-level `README.md` files own module-specific responsibilities and maintenance details.
- File-level docstrings own implementation contracts, parameters, relationships, and edge cases.

The same detailed explanation should not be copied into several documents. Summaries may appear in the root README, but the authoritative detail should live in one clearly named location.

## Release Information

The canonical release version is stored in `version.py` and exposed to the application through `brisart_ai/version_info.py`.

Release history, architectural changes, fixes, known limitations, and verification notes are recorded in [`docs/CHANGELOG.md`](docs/CHANGELOG.md).

## Author

Created and maintained by **Jason Brisart** as part of the Brisart research tooling ecosystem.

## Final Note

BrisartAI is built around a simple principle: research infrastructure should remain understandable to the people who depend on it.

Local storage, inspectable ranking, source-grounded answers, explicit architecture, package-level documentation, and pure-Python implementation all support that goal.
