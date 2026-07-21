# BrisartAI

**Pure Python. No Dependencies. Local-First. Inspectable.**

BrisartAI is a local research assistant that transforms files, folders, notes, archives, project repositories, and web research into a searchable knowledge system.

Unlike cloud-based AI systems, BrisartAI is designed to run locally, store data locally, and remain fully inspectable. Every component is written in standard Python and can be reviewed, modified, and audited.

---

# Philosophy

BrisartAI was built around a simple principle:

```text
Your data should remain your data.
```

The project prioritizes:

- Local-first operation
- Explainable behavior
- Source-grounded answers
- Inspectable code
- Pure Python implementation
- Minimal dependencies
- Optional internet access

Local information is treated as the primary source of truth.

Internet access is optional and exists only to provide additional research context when explicitly enabled.

---

# Core Workflow

```text
Files, Folders, Archives
            │
            ▼
       BrisartAI
            │
            ▼
     Local SQLite Index
            │
            ▼
      Search & Analysis
            │
            ▼
     Source-Grounded Answers
```

---

# Features

## Knowledge Indexing

BrisartAI can ingest:

- Project folders
- Research archives
- Source code repositories
- Notes and documentation
- Configuration files
- Logs and exports
- Saved web pages

All indexed content is stored in a local SQLite database.

---

## Local Search

Search across indexed information using natural language:

```text
What is this project about?

Which files mention preservation?

Summarize the indexed archive.
```

---

## Source-Grounded Responses

When evidence exists, BrisartAI answers using indexed sources.

Responses include:

- Retrieved evidence
- Supporting observations
- Reasoning explanations
- Source references
- Suggested next actions

---

## Analysis

Analyze indexed datasets to identify:

- Recurring themes
- Common terminology
- File distributions
- Project structure patterns
- Potential documentation gaps

---

## Recommendations

Generate recommendations based on indexed information.

Examples include:

- Missing documentation
- Duplicate content
- Large files
- Organizational improvements
- Data hygiene observations

---

## Drive and Folder Scanning

BrisartAI can scan large folder structures for supported content.

The scanner uses conservative defaults and automatically avoids common system, cache, and dependency directories.

---

## Optional Internet Research

BrisartAI can optionally:

- Search public websites
- Crawl approved URLs
- Compare outside information against local data

Internet access is never required.

---

# Supported File Types

## Text and Documentation

- .txt
- .md
- .markdown
- .rst
- .rtf
- .log

## Data Formats

- .csv
- .tsv
- .json
- .jsonl
- .xml
- .yaml
- .yml
- .toml
- .ini
- .cfg
- .conf

## Source Code

- .py
- .js
- .ts
- .jsx
- .tsx
- .java
- .c
- .cpp
- .h
- .cs
- .go
- .rs
- .sh
- .ps1
- .bat
- .sql

## Web Content

- .html
- .htm
- .css
- .svg

## Office Documents

Best-effort pure-Python extraction:

- .docx
- .pptx
- .xlsx
- .odt

## PDF

Best-effort pure-Python extraction:

- .pdf

The objective is searchable text extraction, not perfect document rendering.

---

# Quick Start

Display index status:

```bash
python brisartai.py status
```

Ingest local data:

```bash
python brisartai.py ingest ./my_data
```

Analyze indexed information:

```bash
python brisartai.py analyze
```

Generate recommendations:

```bash
python brisartai.py recommend
```

Ask a question:

```bash
python brisartai.py ask "what is this project about"
```

Launch interactive mode:

```bash
python brisartai.py
```

or

```bash
start.bat
```

---

# Project Structure

```text
brisart_ai/

├── core/
│   ├── conversation engine
│   ├── memory
│   └── assistant interface
│
├── intelligence/
│   ├── self knowledge
│   ├── personality
│   └── freeform conversation
│
├── io/
│   ├── readers
│   ├── extractors
│   └── input processing
│
├── knowledge/
│   ├── indexing
│   ├── retrieval
│   ├── ranking
│   └── synthesis
│
├── scanning/
│   └── drive discovery
│
├── recommendations/
│   └── recommendation engine
│
└── web/
    └── optional internet research
```

This structure keeps subsystems isolated, inspectable, and easy to maintain.

---

# Limitations

BrisartAI is intentionally simple.

Current limitations include:

- Not a large neural model
- Cannot know information that has not been indexed
- Retrieval quality depends on indexed content
- Office and PDF parsing are best-effort
- Internet access may be unavailable in air-gapped environments

---

# Documentation

Additional documentation is available in:

```text
docs/
├── architecture.md
├── commands.md
├── drive_scanning.md
├── file_types.md
├── personality.md
└── safety.md
```

---

# Design Goals

BrisartAI aims to be:

- Local
- Transparent
- Maintainable
- Explainable
- Air-gap friendly
- Dependency free
- Easy to audit

The project favors simplicity and inspectability over complexity and hidden behavior.

---

# License

See `LICENSE` for licensing information.