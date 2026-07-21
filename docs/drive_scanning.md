# Drive Scanning

BrisartAI can scan broad folders or likely drive roots, but the default policy is conservative.

## Preview Candidate Files

```bash
python brisartai.py scan-drive C:\Users\Jason --preview
```

## Ingest Candidate Files

```bash
python brisartai.py scan-drive C:\Users\Jason --max-files 10000
```

## Default Behavior

BrisartAI skips common system, cache, dependency, and hidden folders, including examples like:

- Windows
- Program Files
- ProgramData
- AppData
- node_modules
- .git
- __pycache__
- cache/temp folders

Supported text-like extensions include:

- `.txt`
- `.md`
- `.py`
- `.html`
- `.csv`
- `.log`
- `.ini`
- `.cfg`
- `.rst`

## Recommendation Flow

```bash
python brisartai.py scan-drive C:\Users\Jason --preview
python brisartai.py scan-drive C:\Users\Jason
python brisartai.py recommend
```

Recommendations are generated from indexed local metadata, terms, file types, duplicate hashes, and project-documentation signals.
