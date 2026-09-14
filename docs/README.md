# BrisartAI

Local-first research intelligence for offline, air-gapped, and researcher-controlled environments.

No cloud services. No hosted AI infrastructure. No telemetry. No vendor lock-in. Just Python.

---

# Why This Exists

Modern AI systems are increasingly built around:

- Cloud-hosted inference
- Subscription services
- Proprietary APIs
- Closed ranking systems
- Remote vector databases
- Always-online operation

BrisartAI explores a different approach.

The goal is simple:

If knowledge matters, you should be able to build, search, organize, rank, and verify that knowledge yourself.

BrisartAI is a local research intelligence platform designed around transparency, auditability, and long-term ownership.

Everything stays under your control.

---

# Design Principles

## Local First

Research belongs to the researcher.

Knowledge remains stored locally under your control.

## Offline Capable

BrisartAI continues functioning without internet access.

Public web research is optional, never required.

## Source Grounded

Every answer should be backed by identifiable evidence.

The system retrieves information from indexed sources and returns citations.

## Human Understandable

Ranking systems should be inspectable.

Research workflows should be understandable.

Stored information should remain accessible years later.

## Pure Python

BrisartAI is built entirely with Python's standard library.

No runtime dependencies.

No package managers.

No external frameworks.

## Long-Term Maintainability

The project prioritizes architecture that remains understandable over time.

Features are separated into clearly defined modules with explicit responsibilities.

---

# What BrisartAI Is

BrisartAI is a retrieval-and-research platform.

It is not a hosted AI service.

It is not a cloud application.

It is not a neural model.

Instead, it:

- Imports research material
- Indexes knowledge locally
- Ranks information
- Retrieves evidence
- Synthesizes source-grounded answers
- Preserves research context

The result is a research assistant built around evidence rather than prediction.

---

# Core Capabilities

| Capability | Purpose |
|------------|----------|
| Local Knowledge Index | Search imported research material |
| Research Notes | Store and retrieve researcher-created notes |
| Web Research | Optionally ingest public web information |
| Source-Grounded Answers | Return evidence with citations |
| Brisart Relevance Engine | Custom ranking system |
| Knowledge Vault | Organize research resources |
| Native Stack | Pure-Python foundational technology |

---

# The Brisart Relevance Engine

BrisartAI does not use TF-IDF.

BrisartAI does not use BM25.

Instead it uses the Brisart Relevance Engine.

The engine evaluates:

- Term rarity
- Term presence
- Document shape
- Query coverage
- Intent classification
- Phrase matching
- Title relevance
- Term proximity

The objective is not simply to find matching words.

The objective is to find information that actually answers the question.

---

# The Brisart Native Stack

BrisartAI includes a collection of from-spec, pure-Python implementations of foundational technologies.

These include:

| Module | Purpose |
|----------|----------|
| BrisartHash | SHA-256 |
| BrisartCodec | Base64 |
| BrisartInflate | DEFLATE / zlib |
| BrisartURL | URL processing |
| BrisartJSON | JSON processing |
| BrisartMarkup | HTML processing |
| BrisartRobots | robots.txt processing |

Each implementation is independently verified against the equivalent Python standard library behavior.

---

# Architectural Overview

```text
BrisartAI
│
├── core/
├── io/
├── knowledge/
├── native/
├── ui/
├── web/
│
├── blocklist.py
├── intent.py
├── util.py
└── version_info.py
```

## core/

Conversation routing, settings, and session memory.

## io/

File ingestion and text extraction.

## knowledge/

Indexing, ranking, retrieval, synthesis, and vault systems.

## native/

The Brisart Native Stack.

## ui/

Desktop application layer.

## web/

Optional public web research subsystem.

---

# Desktop Application

BrisartAI uses a modular Tkinter desktop architecture.

The interface remains separate from indexing, storage, ranking, and retrieval logic.

The UI is a presentation layer.

Knowledge systems remain independent.

---

# Testing

BrisartAI includes a repository-wide automated test suite.

Tests are colocated beside source code.

Coverage includes:

- Native modules
- Indexing
- Ranking
- Intent classification
- Knowledge vault systems
- Web logic
- Service layer behavior

Ranking quality is additionally validated using replay fixtures and regression datasets.

---

# Documentation

Core documentation:

- ARCHITECTURE.md
- TESTING.md
- SECURITY.md
- KNOWN_ISSUES.md
- CHANGELOG.md

Package-level documentation exists beside the source it describes.

---

# Licensing

BrisartAI is part of the Brisart ecosystem.

See LICENSE.md for licensing information.

---

# Author

Jason Brisart

Research tooling for local-first and air-gapped research environments.
