# BrisartAI

**Pure Python. No Dependencies. Local-First. Inspectable.**

BrisartAI turns your own files, folders, archives, notes, logs, and saved web pages into a local searchable knowledge system. It can also optionally connect to the internet, search for public results, crawl selected pages, and compare outside information against your local data.

## Core Idea

```text
plug your data in -> BrisartAI indexes it -> ask questions -> get sourced answers
                                      \
                                       optional internet search/crawl
```

## What It Does

- Ingests local folders and files
- Reads `.txt`, `.md`, `.py`, `.html`, `.csv`, `.log`, `.ini`, `.cfg`, `.rst`
- Stores text in local SQLite
- Builds a keyword index
- Analyzes folder contents
- Answers questions from local data
- Cites files and URLs
- Optionally searches the web and crawls public pages
- Uses only Python standard library

## Quick Start

```bash
python brisartai.py status
python brisartai.py ingest ./my_data
python brisartai.py analyze
python brisartai.py ask "what is this data about"
```

Optional internet mode:

```bash
python brisartai.py web "digital preservation fixity checks" --limit 5
python brisartai.py ask "compare my archive workflow with current preservation practices" --web
```

## Important Honesty Note

BrisartAI is not a ChatGPT-scale neural model. It is a local, inspectable, source-grounded research assistant. It retrieves and synthesizes information from indexed data instead of generating unsupported claims from a hidden neural model.

## Version

`0.6.0-alpha`


## Drive Scanning and Recommendations

BrisartAI can now scan broad folders or likely drive roots for supported text-like files.
It is intentionally conservative by default and skips common system, cache, hidden, and dependency folders.

Preview first:

```bash
python brisartai.py scan-drive C:\Users\Jason --preview
```

Ingest after preview:

```bash
python brisartai.py scan-drive C:\Users\Jason --max-files 10000
```

Generate recommendations:

```bash
python brisartai.py recommend
```

Recommendations are based only on indexed data. BrisartAI does not upload your files.


## Living Logical Voice

BrisartAI now has a response layer that makes it feel more like an analytical assistant:

- opens with what it reviewed
- separates observations from evidence
- explains why it reached a conclusion
- gives confidence labels based on retrieval strength
- suggests one practical next move
- keeps local session memory for recent topics

It does **not** claim to be conscious or sentient. The goal is to make it feel present, logical, and useful while staying grounded in inspectable evidence.


## Free-Form Assistant Mode

BrisartAI now responds to anything typed into `ask` or `chat`.

If indexed evidence exists, it answers from imported files and cites sources.
If no indexed evidence matches, it still responds conversationally but clearly says that the answer is not grounded in imported files yet.

```bash
python brisartai.py ask "hello"
python brisartai.py ask "what should I do next"
python brisartai.py chat
```

## Expanded File Types

BrisartAI now supports many more text-like and best-effort readable formats:

- text/docs: `.txt`, `.md`, `.rst`, `.rtf`, `.srt`, `.vtt`
- data/config: `.csv`, `.tsv`, `.json`, `.jsonl`, `.xml`, `.yaml`, `.yml`, `.toml`, `.ini`, `.cfg`, `.conf`, `.env`
- code/scripts: `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.java`, `.c`, `.cpp`, `.h`, `.cs`, `.go`, `.rs`, `.sh`, `.ps1`, `.bat`, `.sql`, `.tex`
- web: `.html`, `.htm`, `.css`, `.svg`
- Office/OpenDocument best-effort: `.docx`, `.pptx`, `.xlsx`, `.odt`
- PDF best-effort: `.pdf`

Office and PDF extraction is pure-Python best effort. It is designed for searchable text, not perfect document rendering.


## v0.6 Chat UX Fix

Running with no arguments now starts BrisartAI directly:

```cmd
py brisartai.py
```

Inside the `BrisartAI>` shell, type normally:

```text
BrisartAI> hello
BrisartAI> what do you do for a living
BrisartAI> can you speak normally without indexed files?
```

You do **not** need to type `py brisartai.py ask` inside chat mode. If you accidentally do, BrisartAI cleans it up and treats it as the actual question.

There is also a Windows launcher:

```cmd
start.bat
```
