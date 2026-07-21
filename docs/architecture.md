# BrisartAI Architecture

BrisartAI is data-first.

```text
Local files/folders
  -> readers.py
  -> ingest.py
  -> index.py
  -> ranker.py
  -> synthesizer.py
  -> assistant.py

Optional internet
  -> crawler.py
  -> index.py
  -> ranker.py
  -> synthesizer.py
```

## Key Principle

Local data is the source of truth. Internet mode is optional context expansion.
