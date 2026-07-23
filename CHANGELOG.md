# Changelog

## 0.8.0-alpha

Added:
- Split the command-line interface into focused modules: commands.py (command handlers), chat.py (interactive shell), and cli.py (argument parser and entry point)
- _clean_sentence() helper in synthesizer.py for readable answer formatting

Changed:
- assistant.py is now a compatibility shim that re-exports the public API, so existing imports such as `from brisart_ai.core.assistant import cmd_chat, main` keep working
- Answer output is now spaced into readable blocks instead of a single wall of text

Fixed:
- Citation numbering is now sequential with no gaps (previously skipped numbers when duplicate passages were removed)
- Removed the noisy tokenized "Context I still have in view" line from answers
  
## 0.7.0-alpha

Added:
- Knowledge Vault layer built on the existing SQLite index
- Research collections for grouping indexed sources
- Local research notes with search
- Lightweight entity extraction and source-to-entity links
- Timeline view around a topic or term
- Vault report and project/research awareness reports

Fixed:
- Corrected a syntax error in io/readers.py that prevented startup
- Aligned package version number with the actual release
  
## 0.6.0-alpha

Fixed:

- Running `py brisartai.py` now starts interactive chat instead of showing help.
- Chat mode now accepts normal human input without requiring `py brisartai.py ask`.
- If the user accidentally types `py brisartai.py ask "hello"` inside chat, BrisartAI now cleans it to `hello`.
- Session memory now stores compact topics instead of huge command strings/full assistant outputs.
- Self-knowledge questions like "what do you do" now use a dedicated self-knowledge module instead of saying no indexed files exist.
- Basic command typos such as `statys`, `stats`, `analyse`, and `char` are corrected.

Added:

- `self_knowledge.py`
- `conversation.py`
- `input_cleaner.py`
- `start.bat`

## 0.5.0-alpha

Added:

- Free-form response mode for any typed input
- Clear distinction between indexed-file answers and general fallback responses
- Much wider file type support
- Pure-Python best-effort readers for `.docx`, `.pptx`, `.xlsx`, `.odt`, and `.pdf`
- Expanded scanner policy for more source/data/code/document formats
- General assistant fallback that explains limits instead of going silent

## 0.4.0-alpha

Added:

- Assistant voice/personality layer
- Logical observations in answers
- Evidence explanations with "Why I think this"
- Confidence labels based on retrieval strength
- Suggested next moves
- Local session memory for recent chat context
- More natural analysis and recommendation output

## 0.3.0-alpha

Added:

- Conservative drive/folder scanning
- Scan preview mode
- Hard limits for max files and max file size
- System/cache/dependency folder exclusions
- Recommendation engine based on indexed data
- Duplicate content detection by hash
- Project hygiene recommendations based on indexed filenames

## 0.2.0-alpha

Shifted BrisartAI from crawler-first to data-first architecture.

## 0.1.0-alpha

Initial crawler/index/retrieval prototype.
