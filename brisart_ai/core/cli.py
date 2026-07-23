"""BrisartAI argument parser and entry point."""
from __future__ import annotations

import argparse
from typing import Optional, Sequence

from brisart_ai.knowledge.index import DEFAULT_DB
from brisart_ai.web.crawler import DEFAULT_DELAY_SECONDS
from brisart_ai.core.chat import cmd_chat
from brisart_ai.core.commands import (
    cmd_analyze,
    cmd_ask,
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
    cmd_scan,
    cmd_status,
    cmd_timeline,
    cmd_vault,
    cmd_vault_rebuild,
    cmd_web,
)


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

    sub.add_parser(
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