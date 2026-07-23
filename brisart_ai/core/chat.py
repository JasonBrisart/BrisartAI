"""BrisartAI interactive chat shell."""
from __future__ import annotations

from brisart_ai import APP_NAME
from brisart_ai.io.input_cleaner import normalize_shellish_input
from brisart_ai.scanning.drive_scanner import default_scan_roots, scan_preview
from brisart_ai.web.crawler import DEFAULT_DELAY_SECONDS
from brisart_ai.core.commands import (
    build_answer,
    cmd_analyze,
    cmd_collection_add,
    cmd_collection_create,
    cmd_collection_list,
    cmd_crawl,
    cmd_ingest,
    cmd_note_add,
    cmd_note_list,
    cmd_note_search,
    cmd_project,
    cmd_recommend,
    cmd_research_report,
    cmd_status,
    cmd_timeline,
    cmd_vault,
    cmd_vault_rebuild,
    cmd_web,
)


def _run_chat_command(line: str, db_path: str, limit: int) -> bool:
    lowered = line.lower().strip()

    if lowered in {"/exit", "exit", "quit"}:
        return False

    if lowered in {"/status", "status", "stats"}:
        cmd_status(db_path)

    elif lowered in {"/analyze", "analyze", "analyse"}:
        cmd_analyze(db_path, top_terms=25)

    elif lowered in {"/recommend", "recommend", "rec", "recs"}:
        cmd_recommend(db_path, top_terms=20)

    elif lowered in {"/project", "project"}:
        cmd_project(db_path)

    elif lowered in {"/research-report", "research-report", "report"}:
        cmd_research_report(db_path, top_terms=35)

    elif lowered in {"/vault", "vault"}:
        cmd_vault(db_path)

    elif lowered in {"/vault rebuild", "vault rebuild"}:
        cmd_vault_rebuild(db_path)

    elif lowered in {"/collections", "collections", "collection list"}:
        cmd_collection_list(db_path)

    elif lowered.startswith("/timeline "):
        topic = line.split(" ", 1)[1].strip()
        cmd_timeline(db_path, topic, limit=30)

    elif lowered.startswith("timeline "):
        topic = line.split(" ", 1)[1].strip()
        cmd_timeline(db_path, topic, limit=30)

    elif lowered.startswith("/collection create "):
        name = line.split(" ", 2)[2].strip()
        cmd_collection_create(db_path, name, "")

    elif lowered.startswith("collection create "):
        name = line.split(" ", 2)[2].strip()
        cmd_collection_create(db_path, name, "")

    elif lowered.startswith("/collection add "):
        rest = line.split(" ", 2)[2].strip()
        if " " not in rest:
            print("Usage: collection add NAME query terms")
        else:
            name, query = rest.split(" ", 1)
            cmd_collection_add(db_path, name, query)

    elif lowered.startswith("collection add "):
        rest = line.split(" ", 2)[2].strip()
        if " " not in rest:
            print("Usage: collection add NAME query terms")
        else:
            name, query = rest.split(" ", 1)
            cmd_collection_add(db_path, name, query)

    elif lowered.startswith("/note add "):
        body = line.split(" ", 2)[2].strip()
        cmd_note_add(db_path, "Chat Note", body, "")

    elif lowered.startswith("note add "):
        body = line.split(" ", 2)[2].strip()
        cmd_note_add(db_path, "Chat Note", body, "")

    elif lowered in {"/note list", "note list", "notes"}:
        cmd_note_list(db_path, limit=20)

    elif lowered.startswith("/note search "):
        query = line.split(" ", 2)[2].strip()
        cmd_note_search(db_path, query, limit=10)

    elif lowered.startswith("note search "):
        query = line.split(" ", 2)[2].strip()
        cmd_note_search(db_path, query, limit=10)

    elif lowered.startswith("/scan-preview"):
        rest = line.split(" ", 1)[1].strip() if " " in line else ""
        roots = [rest] if rest else default_scan_roots()
        print(scan_preview(roots, max_files=1000))

    elif lowered.startswith("/ingest "):
        cmd_ingest([line.split(" ", 1)[1].strip()], db_path)

    elif lowered.startswith("/web "):
        cmd_web(
            line.split(" ", 1)[1].strip(),
            db_path,
            limit=5,
            depth=0,
        )

    elif lowered.startswith("/crawl "):
        cmd_crawl(
            [line.split(" ", 1)[1].strip()],
            db_path,
            limit=10,
            depth=0,
            delay=DEFAULT_DELAY_SECONDS,
            cross_domain=False,
        )

    else:
        print(
            build_answer(
                line,
                db_path,
                limit=limit,
                use_web=False,
                web_limit=3,
            )
        )

    return True


def cmd_chat(db_path: str, limit: int) -> None:
    print(f"{APP_NAME} interactive mode")
    print(
        "Type normally. You do not need to type "
        "`py brisartai.py ask` inside this shell."
    )
    print("")
    print("Commands:")
    print("- /status")
    print("- /ingest PATH")
    print("- /scan-preview PATH")
    print("- /analyze")
    print("- /recommend")
    print("- /project")
    print("- /research-report")
    print("- /vault")
    print("- /vault rebuild")
    print("- /timeline TOPIC")
    print("- /collection create NAME")
    print("- /collection add NAME QUERY")
    print("- /note add TEXT")
    print("- /note list")
    print("- /note search QUERY")
    print("- /web QUERY")
    print("- /crawl URL")
    print("- /exit")

    while True:
        try:
            raw = input("\nBrisartAI> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return

        line = normalize_shellish_input(raw)

        if not _run_chat_command(line, db_path, limit):
            return