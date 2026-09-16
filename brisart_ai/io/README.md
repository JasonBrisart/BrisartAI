# brisart_ai/io/

Local file reading: deciding what BrisartAI can ingest, walking folders to find it, and extracting searchable text from every supported format. Pure standard library throughout — no third-party parsing libraries anywhere in this folder.

```text
io/
├── readers.py           File-type dispatch and folder walking (the entry point)
├── binary_readers.py    Office (.docx/.pptx/.xlsx/.odt) and PDF extraction
├── extractor.py         HTML → text + link extraction; CSV → searchable text
└── input_cleaner.py     Chat-box input normalization
```

---

## `readers.py`

`is_supported()` decides which files BrisartAI can read at all, checked against `SUPPORTED_EXTENSIONS` (the union of `TEXT_EXTENSIONS` and `BINARY_TEXT_EXTENSIONS`) plus a small set of well-known extensionless filenames (`dockerfile`, `makefile`, `license`, `readme`, `changelog`), matched case-insensitively.

`iter_supported_files()` walks a mix of individual paths and folders recursively, de-duplicating by resolved path so the same file reached via two input paths is only yielded once. It silently skips anything it can't resolve or access rather than aborting the run.

`read_file()` extracts searchable text from one supported file: `.docx`/`.pptx`/`.xlsx`/`.odt`/`.pdf` delegate to `binary_readers.py`; `.html`/`.htm`/`.svg` and `.csv` delegate to `extractor.py`; a few lighter formats (`.json`, `.jsonl`, `.rtf`, `.tsv`) are handled inline — `.rtf` gets a deliberately crude regex stripper, and `.json`/`.jsonl` are pretty-printed when parseable via the native `brisart_json`, returned as-is otherwise, never raising on invalid JSON.

---

## `binary_readers.py`

Best-effort, non-rendering text extraction — the goal throughout is *searchable text*, not faithful visual reproduction:

- **`.docx`/`.pptx`/`.xlsx`/`.odt`** are ZIP containers holding XML parts; each reader unzips the relevant parts (Word: all of `word/*.xml`; PowerPoint: slides *and* notes slides, so speaker notes are searchable; Excel: `sharedStrings.xml` plus every worksheet; ODT: `content.xml`) and pulls text nodes out with `xml.etree.ElementTree`.
- **`.pdf`** (`read_pdf_best_effort()`) is a hand-rolled, non-rendering scraper: it finds literal parenthesized text runs directly in the raw bytes, then separately decompresses any `stream…endstream` block it can via the native `brisart_inflate` (replacing `zlib.decompress()`) and pulls parenthesized runs out of that too. Capped at 10 MB scanned per file.

Every function returns an empty string on any failure rather than raising — callers treat empty text as "nothing to index," so one bad file never blocks an import.

---

## `extractor.py`

`HTMLTextExtractor` (a `native.brisart_markup.BrisartMarkupParser` subclass) skips `<script>`/`<style>`/`<svg>`/`<canvas>`/`<template>` entirely, inserts a newline at block-level tag boundaries so paragraphs and list items don't run together, and collects `<a href>` targets (resolved against `base_url` via the native `brisart_url`, de-duplicated, http(s)-only) as a side channel of discovered links for the crawler.

One deliberate special case: `<sup class="reference">[3]</sup>` — the MediaWiki-style footnote marker Wikipedia and its mirrors use — is skipped, scoped narrowly to `<sup>` tags carrying a reference/citation-style class, so an ordinary superscript like "10²" is untouched.

`csv_to_text()` converts each row to a pipe-separated line via `csv.reader`, falling back to a naive comma-to-pipe split if the CSV is malformed enough to make `csv.reader` choke.

---

## `input_cleaner.py`

Trims whitespace and unwraps one pair of matching quotes around a pasted question. The chat box only ever receives questions, never commands, so this deliberately does no shell-syntax or typo correction.
