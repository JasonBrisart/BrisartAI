# BrisartAI

**Local Research Intelligence. Pure Python. Zero Dependencies.**

BrisartAI is a desktop research assistant that transforms files, notes, documentation, source code, and optional public web research into a searchable, source-grounded knowledge system.

No cloud services.

No subscriptions.

No proprietary AI APIs.

No third-party dependencies.

Just Python.

---

## Why BrisartAI Exists

Modern research tools increasingly depend on:

- Cloud infrastructure
- Hosted AI services
- Vector databases
- Telemetry pipelines
- Large dependency chains

BrisartAI was built around a different philosophy:

- Local-first operation
- Complete transparency
- Long-term maintainability
- Air-gapped compatibility
- Source-grounded answers
- Dependency-free deployment

The result is a research assistant that operates identically on:

- Personal workstations
- Research laptops
- Secure institutional systems
- Air-gapped laboratory environments

---

## Core Capabilities

### Research Your Own Data

Import:

- Documents
- Notes
- Research archives
- Source code
- Technical documentation
- Configuration files
- Historical records

BrisartAI indexes them into a local SQLite knowledge base for rapid retrieval and analysis.

---

### Source-Grounded Answers

Answers are generated from indexed evidence.

Every answer includes source attribution.

BrisartAI does not invent citations.

If evidence does not exist, the system says so.

---

### Optional Public Web Research

When enabled, BrisartAI can:

- Search multiple public search providers
- Respect robots.txt policies
- Filter low-quality results
- Index useful pages locally
- Combine public information with local research

When disabled, BrisartAI operates entirely offline.

---

### The Brisart Relevance Engine

BrisartAI includes a custom retrieval system designed specifically for local research collections.

The ranking engine evaluates:

- Term rarity
- Document focus
- Query coverage
- Title relevance
- Phrase matching
- Term proximity
- Question intent

The objective is simple:

> Rank documents because they answer the question, not because they merely contain the words.

---

## Built For

BrisartAI was designed for:

- Researchers
- Scientists
- Historians
- Writers
- Engineers
- Analysts
- Students
- Independent investigators
- Research laboratories
- Digital preservation environments
- Air-gapped systems

---

## Supported Formats

### Text and Documentation

- TXT
- Markdown
- HTML
- XML
- CSV
- TSV
- JSON
- YAML
- TOML
- INI
- Configuration files
- Log files

### Source Code

- Python
- JavaScript
- TypeScript
- Java
- C
- C++
- C#
- Go
- Rust
- Shell Scripts
- SQL

### Office and Research Formats

- PDF
- DOCX
- PPTX
- XLSX
- ODT

See `docs/file_types.md` for the complete format list.

---

## The Brisart Native Stack

BrisartAI includes custom pure-Python implementations of the infrastructure it depends on.

Modules include:

- SHA-256 hashing
- URL parsing
- JSON processing
- Base64 encoding
- HTML tokenization
- Robots.txt handling
- DEFLATE decompression

Each implementation was independently verified against the corresponding Python standard library implementation before integration.

The result is a completely inspectable, dependency-free codebase.

---

## Architecture

```text
Files / Notes / Web Pages
            │
            ▼
     Local SQLite Index
            │
            ▼
 Brisart Relevance Engine
            │
            ▼
 Source-Grounded Answers
            │
            ▼
          Desktop UI
```

Everything operates locally.

There is no remote backend.

There is no hosted service.

There is no telemetry pipeline.

---

## Project Structure

```text
BrisartAI/
│
├── brisart_ai/
│   ├── core/
│   ├── io/
│   ├── knowledge/
│   ├── native/
│   ├── ui/
│   ├── web/
│   ├── blocklist.py
│   ├── intent.py
│   ├── util.py
│   └── version_info.py
│
├── data/
├── docs/
├── scripts/
│
├── run.py
├── version.py
└── README.md
```

Every major subsystem contains its own documentation and co-located test suite.

---

## Installation

```bash
git clone <repository>
cd BrisartAI
python run.py
```

No package installation required.

No dependency management required.

No external services required.

---

## Documentation

- `docs/ARCHITECTURE.md`
- `docs/SECURITY.md`
- `docs/TESTING.md`
- `docs/KNOWN_ISSUES.md`
- `docs/CHANGELOG.md`
- `docs/file_types.md`

Additional subsystem documentation exists throughout the repository.

---

## Design Principles

### Local First

Your research remains under your control.

### Source Grounded

Answers must be supported by evidence.

### Dependency Free

The Python standard library is enough.

### Transparent

The entire system can be inspected and audited.

### Air-Gap Friendly

Offline operation is a first-class deployment target.

### Maintainable

Built to remain understandable years from now.

---

## No Vendor Lock-In

BrisartAI stores information in:

- Plain files
- SQLite databases
- Human-readable formats

Your research is not trapped behind a hosted platform.

---

## License

See `LICENSE`.
