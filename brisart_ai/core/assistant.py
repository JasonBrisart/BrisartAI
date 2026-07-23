"""BrisartAI command-line interface.

Feature layers (see CHANGELOG.md for version history):
- Knowledge Vault
- Research Collections
- Research Notes
- Project Awareness
- Timelines
- Research Reports

This file intentionally uses absolute imports so the reorganized package
layout remains clear and inspectable.
"""

from __future__ import annotations

import argparse
from typing import Optional, Sequence

from brisart_ai import APP_NAME, __version__
from brisart_ai.intelligence.freeform import freeform_response
from brisart_ai.core.conversation import build_conversation_answer
from brisart_ai.core.session_memory import SessionMemory
from brisart_ai.io.input_cleaner import normalize_shellish_input
from brisart_ai.knowledge.analyzer import analyze_index
from brisart_ai.knowledge.index import DEFAULT_DB, Index
from brisart_ai.knowledge.ingest import ingest_paths
from brisart_ai.knowledge.project_awareness import project_report, research_report
from brisart_ai.knowledge.ranker import search
from brisart_ai.knowledge.vault import (
    add_note,
    add_sources_to_collection,
    create_collection,
    list_collections,
    list_notes,
    rebuild_entities,
    search_notes,
    timeline,
    vault_report,
)
from brisart_ai.recommendations.recommender import recommend
from brisart_ai.scanning.drive_scanner import (
    default_scan_roots,
    scan_and_ingest,
    scan_preview,
)
from brisart_ai.web.crawler import (
    DEFAULT_DELAY_SECONDS,
    crawl_urls_to_index,
    web_search_and_ingest,
)


def cmd_status(db_path: str) -> None:
    index = Index(db_path)
    try:
        print(f"{APP_NAME} {__version__}")
        print("Pure Python. No Dependencies. Local-First. Inspectable.")
        print(f"Database: {db_path}")
        print(f"Indexed sources: {index.source_count()}")
        print(f"Local files: {index.source_count('file')}")
        print(f"Web pages: {index.source_count('web')}")
        print("")
        print("Major systems:")
        print("- Local file ingestion")
        print("- SQLite knowledge index")
        print("- Source-grounded answers")
        print("- Knowledge vault")
        print("- Research collections")
        print("- Local research notes")
        print("- Optional web research")
    finally:
        index.close()


def cmd_ingest(paths, db_path: str) -> None:
    index = Index(db_path)
    try:
        count = ingest_paths(paths, index)
        print(f"Done. Ingested local files this run: {count}")
        print(f"Indexed sources total: {index.source_count()}")
    finally:
        index.close()


def cmd_scan(
    paths,
    db_path: str,
    preview: bool,
    include_hidden: bool,
    max_files: int,
    max_file_bytes: int,
) -> None:
    roots = paths or default_scan_roots()

    if preview:
        print(
            scan_preview(
                roots,
                include_hidden=include_hidden,
                max_files=max_files,
                max_file_bytes=max_file_bytes,
            )
        )
        return

    index = Index(db_path)

    try:
        count = scan_and_ingest(
            roots,
            index,
            include_hidden=include_hidden,
            max_files=max_files,
            max_file_bytes=max_file_bytes,
        )
        print(f"Done. Drive scan ingested files this run: {count}")
        print(f"Indexed sources total: {index.source_count()}")
    finally:
        index.close()


def cmd_analyze(db_path: str, top_terms: int) -> None:
    index = Index(db_path)
    try:
        print(analyze_index(index, top_terms=top_terms))
    finally:
        index.close()


def cmd_recommend(db_path: str, top_terms: int) -> None:
    index = Index(db_path)
    try:
        print(recommend(index, top_terms=top_terms))
    finally:
        index.close()


def cmd_web(query: str, db_path: str, limit: int, depth: int) -> None:
    index = Index(db_path)
    try:
        count = web_search_and_ingest(
            query,
            index,
            limit=limit,
            crawl_depth=depth,
        )
        print(f"Done. Web pages indexed this run: {count}")
        print(f"Indexed sources total: {index.source_count()}")
    finally:
        index.close()


def cmd_crawl(
    urls,
    db_path: str,
    limit: int,
    depth: int,
    delay: float,
    cross_domain: bool,
) -> None:
    index = Index(db_path)
    try:
        count = crawl_urls_to_index(
            urls,
            index,
            limit=limit,
            depth=depth,
            delay=delay,
            same_domain_only=not cross_domain,
        )
        print(f"Done. Web pages indexed this run: {count}")
    finally:
        index.close()


def build_answer(
    query: str,
    db_path: str,
    limit: int,
    use_web: bool,
    web_limit: int,
) -> str:
    cleaned = normalize_shellish_input(query)
    index = Index(db_path)
    memory = SessionMemory(db_path)

    try:
        header = ""

        if use_web:
            header = (
                "Internet mode enabled. Searching public web before answering.\n"
            )
            web_search_and_ingest(
                cleaned,
                index,
                limit=web_limit,
                crawl_depth=0,
            )

        return header + build_conversation_answer(
            cleaned,
            index,
            memory,
            limit=limit,
        )
    finally:
        memory.close()
        index.close()


def cmd_ask(
    query: str,
    db_path: str,
    limit: int,
    use_web: bool,
    web_limit: int,
) -> None:
    print(build_answer(query, db_path, limit, use_web, web_limit))


def cmd_project(db_path: str) -> None:
    index = Index(db_path)
    try:
        print(project_report(index))
    finally:
        index.close()


def cmd_research_report(db_path: str, top_terms: int) -> None:
    index = Index(db_path)
    try:
        print(research_report(index, top_terms=top_terms))
    finally:
        index.close()


def cmd_vault(db_path: str) -> None:
    index = Index(db_path)
    try:
        print(vault_report(index))
    finally:
        index.close()


def cmd_vault_rebuild(db_path: str) -> None:
    index = Index(db_path)
    try:
        print(rebuild_entities(index))
    finally:
        index.close()


def cmd_timeline(db_path: str, query: str, limit: int) -> None:
    index = Index(db_path)
    try:
        print(timeline(index, query, limit=limit))
    finally:
        index.close()


def cmd_collection_create(
    db_path: str,
    name: str,
    description: str,
) -> None:
    index = Index(db_path)
    try:
        print(create_collection(index, name, description))
    finally:
        index.close()


def cmd_collection_list(db_path: str) -> None:
    index = Index(db_path)
    try:
        print(list_collections(index))
    finally:
        index.close()


def cmd_collection_add(
    db_path: str,
    name: str,
    query: str,
) -> None:
    index = Index(db_path)
    try:
        print(add_sources_to_collection(index, name, query))
    finally:
        index.close()


def cmd_note_add(
    db_path: str,
    title: str,
    body: str,
    collection: str,
) -> None:
    index = Index(db_path)
    try:
        print(add_note(index, title, body, collection))
    finally:
        index.close()


def cmd_note_list(db_path: str, limit: int) -> None:
    index = Index(db_path)
    try:
        print(list_notes(index, limit=limit))
    finally:
        index.close()


def cmd_note_search(db_path: str, query: str, limit: int) -> None:
    index = Index(db_path)
    try:
        print(search_notes(index, query, limit=limit))
    finally:
        index.close()


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="BrisartAI pure-Python local research assistant"
    )

    parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help="SQLite database path",
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="show index status")

    ingest = sub.add_parser("ingest", help="ingest local files or folders")
    ingest.add_argument("paths", nargs="+", help="file or folder paths")

    scan = sub.add_parser(
        "scan-drive",
        help="preview or ingest supported files from broad drive/folder scan",
    )
    scan.add_argument(
        "paths",
        nargs="*",
        help="roots to scan. If omitted, BrisartAI chooses likely local roots",
    )
    scan.add_argument(
        "--preview",
        action="store_true",
        help="show candidate files without indexing them",
    )
    scan.add_argument(
        "--include-hidden",
        action="store_true",
        help="include hidden dotfiles and dotfolders",
    )
    scan.add_argument(
        "--max-files",
        type=int,
        default=10000,
        help="maximum candidate files",
    )
    scan.add_argument(
        "--max-file-bytes",
        type=int,
        default=10_000_000,
        help="maximum individual file size",
    )

    analyze = sub.add_parser("analyze", help="analyze indexed data")
    analyze.add_argument(
        "--top-terms",
        type=int,
        default=25,
        help="number of top terms to show",
    )

    recommend_cmd = sub.add_parser(
        "recommend",
        help="make recommendations from indexed data",
    )
    recommend_cmd.add_argument(
        "--top-terms",
        type=int,
        default=20,
        help="number of top terms to show",
    )

    ask = sub.add_parser(
        "ask",
        help="ask anything. BrisartAI answers from indexed data when possible",
    )
    ask.add_argument("query", help="question or message")
    ask.add_argument(
        "--limit",
        type=int,
        default=8,
        help="number of retrieved sources",
    )
    ask.add_argument(
        "--web",
        action="store_true",
        help="search public web before answering",
    )
    ask.add_argument(
        "--web-limit",
        type=int,
        default=3,
        help="web results to ingest before answering",
    )

    web = sub.add_parser(
        "web",
        help="search public web and ingest result pages",
    )
    web.add_argument("query", help="public web search query")
    web.add_argument(
        "--limit",
        type=int,
        default=5,
        help="number of search results to ingest",
    )
    web.add_argument(
        "--depth",
        type=int,
        default=0,
        help="link crawl depth from result pages",
    )

    crawl = sub.add_parser("crawl", help="crawl specific public URLs")
    crawl.add_argument("urls", nargs="+", help="URLs to crawl")
    crawl.add_argument(
        "--limit",
        type=int,
        default=20,
        help="maximum pages",
    )
    crawl.add_argument(
        "--depth",
        type=int,
        default=0,
        help="link depth",
    )
    crawl.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help="delay between requests",
    )
    crawl.add_argument(
        "--cross-domain",
        action="store_true",
        help="follow links off the original domain",
    )

    sub.add_parser("project", help="show project awareness report")
    sub.add_parser("vault", help="show knowledge vault report")

    vault_rebuild = sub.add_parser(
        "vault-rebuild",
        help="rebuild simple entity index",
    )

    timeline_cmd = sub.add_parser(
        "timeline",
        help="show timeline around a topic",
    )
    timeline_cmd.add_argument("query", help="topic or concept")
    timeline_cmd.add_argument(
        "--limit",
        type=int,
        default=30,
        help="maximum matched sources",
    )

    report = sub.add_parser(
        "research-report",
        help="generate research intelligence report",
    )
    report.add_argument(
        "--top-terms",
        type=int,
        default=35,
        help="number of top terms to show",
    )

    collection = sub.add_parser(
        "collection",
        help="manage research collections",
    )
    collection_sub = collection.add_subparsers(dest="collection_command")

    collection_create = collection_sub.add_parser(
        "create",
        help="create a collection",
    )
    collection_create.add_argument("name")
    collection_create.add_argument(
        "--description",
        default="",
    )

    collection_sub.add_parser(
        "list",
        help="list collections",
    )

    collection_add = collection_sub.add_parser(
        "add",
        help="add matching sources to a collection",
    )
    collection_add.add_argument("name")
    collection_add.add_argument("query")

    note = sub.add_parser("note", help="manage local research notes")
    note_sub = note.add_subparsers(dest="note_command")

    note_add = note_sub.add_parser("add", help="add a note")
    note_add.add_argument("title")
    note_add.add_argument("body")
    note_add.add_argument(
        "--collection",
        default="",
    )

    note_list = note_sub.add_parser("list", help="list notes")
    note_list.add_argument(
        "--limit",
        type=int,
        default=20,
    )

    note_search = note_sub.add_parser("search", help="search notes")
    note_search.add_argument("query")
    note_search.add_argument(
        "--limit",
        type=int,
        default=10,
    )

    chat = sub.add_parser("chat", help="interactive shell")
    chat.add_argument(
        "--limit",
        type=int,
        default=8,
        help="number of retrieved sources",
    )

    return parser


def _correct_command_alias(argv):
    if not argv:
        return argv

    aliases = {
        "statys": "status",
        "stats": "status",
        "analyse": "analyze",
        "rec": "recommend",
        "recs": "recommend",
        "char": "chat",
        "report": "research-report",
    }

    fixed = list(argv)

    if fixed[0] in aliases:
        fixed[0] = aliases[fixed[0]]

    return fixed


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()

    raw = list(argv) if argv is not None else None

    if raw is not None:
        raw = _correct_command_alias(raw)

    args = parser.parse_args(raw)

    if args.command == "status":
        cmd_status(args.db)

    elif args.command == "ingest":
        cmd_ingest(args.paths, args.db)

    elif args.command == "scan-drive":
        cmd_scan(
            args.paths,
            args.db,
            args.preview,
            args.include_hidden,
            args.max_files,
            args.max_file_bytes,
        )

    elif args.command == "analyze":
        cmd_analyze(args.db, args.top_terms)

    elif args.command == "recommend":
        cmd_recommend(args.db, args.top_terms)

    elif args.command == "ask":
        cmd_ask(
            args.query,
            args.db,
            args.limit,
            args.web,
            args.web_limit,
        )

    elif args.command == "web":
        cmd_web(
            args.query,
            args.db,
            args.limit,
            args.depth,
        )

    elif args.command == "crawl":
        cmd_crawl(
            args.urls,
            args.db,
            args.limit,
            args.depth,
            args.delay,
            args.cross_domain,
        )

    elif args.command == "project":
        cmd_project(args.db)

    elif args.command == "vault":
        cmd_vault(args.db)

    elif args.command == "vault-rebuild":
        cmd_vault_rebuild(args.db)

    elif args.command == "timeline":
        cmd_timeline(args.db, args.query, args.limit)

    elif args.command == "research-report":
        cmd_research_report(args.db, args.top_terms)

    elif args.command == "collection":
        if args.collection_command == "create":
            cmd_collection_create(
                args.db,
                args.name,
                args.description,
            )
        elif args.collection_command == "list":
            cmd_collection_list(args.db)
        elif args.collection_command == "add":
            cmd_collection_add(
                args.db,
                args.name,
                args.query,
            )
        else:
            parser.print_help()

    elif args.command == "note":
        if args.note_command == "add":
            cmd_note_add(
                args.db,
                args.title,
                args.body,
                args.collection,
            )
        elif args.note_command == "list":
            cmd_note_list(args.db, args.limit)
        elif args.note_command == "search":
            cmd_note_search(
                args.db,
                args.query,
                args.limit,
            )
        else:
            parser.print_help()

    elif args.command == "chat":
        cmd_chat(args.db, args.limit)

    else:
        cmd_chat(args.db, 8)

    return 0