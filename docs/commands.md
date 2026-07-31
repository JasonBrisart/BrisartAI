# BrisartAI Commands

## Core commands (chat mode)

These are the only five things a new user ever needs to know:

```text
import PATH        import local files or a folder
note TEXT           save a research note
research QUERY      search the public web on demand
settings            view or toggle research sources
help                show everything, including advanced commands
```

You do not need a command to ask a question. Just type it:

```text
BrisartAI> what is this project about
```

BrisartAI automatically searches your local knowledge base first. If
Automatic Web Research is turned on (`settings`), it will also search
the public web when no local evidence is found.

## Research settings

```text
BrisartAI> settings
```

Toggle Automatic Web Research or the other tracked sources:

```text
BrisartAI> settings web
BrisartAI> settings local
BrisartAI> settings notes
BrisartAI> settings collections
```

Only `web` (Automatic Web Research) changes routing behavior today.
Local Files, Notes, and Collections are always part of your local
knowledge base; those toggles are tracked for future use and reported
honestly as such in `settings` output.

## Advanced commands

Everything BrisartAI has always supported is still here, just moved
out of the beginner-facing help text:

```bash
python brisartai.py status
python brisartai.py ingest ./data
python brisartai.py scan-drive C:\Users\Jason --preview
python brisartai.py analyze
python brisartai.py recommend
python brisartai.py ask "what is this project about"
python brisartai.py web "digital preservation fixity checks" --limit 5
python brisartai.py research "digital preservation fixity checks" --limit 5
python brisartai.py ask "compare my archive workflow with public preservation practices" --web
python brisartai.py project
python brisartai.py vault
python brisartai.py vault-rebuild
python brisartai.py timeline "TOPIC"
python brisartai.py research-report
python brisartai.py collection create NAME
python brisartai.py collection add NAME "query terms"
python brisartai.py collection list
python brisartai.py note add "Title" "Body text"
python brisartai.py note list
python brisartai.py note search "query"
python brisartai.py settings show
python brisartai.py settings toggle web
python brisartai.py crawl https://example.com --limit 10
```

`web` and `research` are aliases of the same command, kept so
existing muscle memory and scripts still work.
