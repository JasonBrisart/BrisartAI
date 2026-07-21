"""BrisartAI command-line interface."""

from __future__ import annotations

import argparse
from typing import Optional, Sequence

from . import APP_NAME, __version__
from .analyzer import analyze_index
from .conversation import build_conversation_answer
from .crawler import DEFAULT_DELAY_SECONDS, crawl_urls_to_index, web_search_and_ingest
from .drive_scanner import default_scan_roots, scan_and_ingest, scan_preview
from .index import DEFAULT_DB, Index
from .ingest import ingest_paths
from .input_cleaner import normalize_shellish_input
from .recommender import recommend
from .session_memory import SessionMemory


def cmd_status(db_path: str) -> None:
    index = Index(db_path)
    try:
        print(f"{APP_NAME} {__version__}")
        print("Pure Python. No Dependencies. Local-First. Inspectable.")
        print(f"Database: {db_path}")
        print(f"Indexed sources: {index.source_count()}")
        print(f"Local files: {index.source_count('file')}")
        print(f"Web pages: {index.source_count('web')}")
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


def cmd_scan(paths, db_path: str, preview: bool, include_hidden: bool, max_files: int, max_file_bytes: int) -> None:
    roots = paths or default_scan_roots()
    if preview:
        print(scan_preview(roots, include_hidden=include_hidden, max_files=max_files, max_file_bytes=max_file_bytes))
        return
    index = Index(db_path)
    try:
        count = scan_and_ingest(roots, index, include_hidden=include_hidden, max_files=max_files, max_file_bytes=max_file_bytes)
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
        count = web_search_and_ingest(query, index, limit=limit, crawl_depth=depth)
        print(f"Done. Web pages indexed this run: {count}")
        print(f"Indexed sources total: {index.source_count()}")
    finally:
        index.close()


def cmd_crawl(urls, db_path: str, limit: int, depth: int, delay: float, cross_domain: bool) -> None:
    index = Index(db_path)
    try:
        count = crawl_urls_to_index(urls, index, limit=limit, depth=depth, delay=delay, same_domain_only=not cross_domain)
        print(f"Done. Web pages indexed this run: {count}")
    finally:
        index.close()


def build_answer(query: str, db_path: str, limit: int, use_web: bool, web_limit: int) -> str:
    cleaned = normalize_shellish_input(query)
    index = Index(db_path)
    memory = SessionMemory(db_path)
    try:
        header = ""
        if use_web:
            header = "Internet mode enabled. Searching public web before answering.\n"
            web_search_and_ingest(cleaned, index, limit=web_limit, crawl_depth=0)
        return header + build_conversation_answer(cleaned, index, memory, limit=limit)
    finally:
        memory.close()
        index.close()


def cmd_ask(query: str, db_path: str, limit: int, use_web: bool, web_limit: int) -> None:
    print(build_answer(query, db_path, limit, use_web, web_limit))


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
    elif lowered.startswith("/scan-preview"):
        rest = line.split(" ", 1)[1].strip() if " " in line else ""
        roots = [rest] if rest else default_scan_roots()
        print(scan_preview(roots, max_files=1000))
    elif lowered.startswith("/ingest "):
        cmd_ingest([line.split(" ", 1)[1].strip()], db_path)
    elif lowered.startswith("/web "):
        cmd_web(line.split(" ", 1)[1].strip(), db_path, limit=5, depth=0)
    elif lowered.startswith("/crawl "):
        cmd_crawl([line.split(" ", 1)[1].strip()], db_path, limit=10, depth=0, delay=DEFAULT_DELAY_SECONDS, cross_domain=False)
    else:
        print(build_answer(line, db_path, limit=limit, use_web=False, web_limit=3))
    return True


def cmd_chat(db_path: str, limit: int) -> None:
    print(f"{APP_NAME} interactive mode")
    print("Type normally. You do not need to type `py brisartai.py ask` inside this shell.")
    print("Commands: /ingest PATH, /scan-preview PATH, /recommend, /web QUERY, /crawl URL, /analyze, /status, /exit")
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
    parser = argparse.ArgumentParser(description="BrisartAI pure-Python local research assistant")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite database path")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="show index status")
    ingest = sub.add_parser("ingest", help="ingest local files or folders")
    ingest.add_argument("paths", nargs="+", help="file or folder paths")

    scan = sub.add_parser("scan-drive", help="preview or ingest supported files from broad drive/folder scan")
    scan.add_argument("paths", nargs="*", help="roots to scan. If omitted, BrisartAI chooses likely local roots")
    scan.add_argument("--preview", action="store_true", help="show candidate files without indexing them")
    scan.add_argument("--include-hidden", action="store_true", help="include hidden dotfiles and dotfolders")
    scan.add_argument("--max-files", type=int, default=10000, help="maximum candidate files")
    scan.add_argument("--max-file-bytes", type=int, default=10_000_000, help="maximum individual file size")

    analyze = sub.add_parser("analyze", help="analyze indexed data")
    analyze.add_argument("--top-terms", type=int, default=25, help="number of top terms to show")

    recommend_cmd = sub.add_parser("recommend", help="make recommendations from indexed data")
    recommend_cmd.add_argument("--top-terms", type=int, default=20, help="number of top terms to show")

    ask = sub.add_parser("ask", help="ask anything. BrisartAI answers from indexed data when possible")
    ask.add_argument("query", help="question or message")
    ask.add_argument("--limit", type=int, default=8, help="number of retrieved sources")
    ask.add_argument("--web", action="store_true", help="search public web before answering")
    ask.add_argument("--web-limit", type=int, default=3, help="web results to ingest before answering")

    web = sub.add_parser("web", help="search public web and ingest result pages")
    web.add_argument("query", help="public web search query")
    web.add_argument("--limit", type=int, default=5, help="number of search results to ingest")
    web.add_argument("--depth", type=int, default=0, help="link crawl depth from result pages")

    crawl = sub.add_parser("crawl", help="crawl specific public URLs")
    crawl.add_argument("urls", nargs="+", help="URLs to crawl")
    crawl.add_argument("--limit", type=int, default=20, help="maximum pages")
    crawl.add_argument("--depth", type=int, default=0, help="link depth")
    crawl.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS, help="delay between requests")
    crawl.add_argument("--cross-domain", action="store_true", help="follow links off the original domain")

    chat = sub.add_parser("chat", help="interactive shell")
    chat.add_argument("--limit", type=int, default=8, help="number of retrieved sources")
    return parser


def _correct_command_alias(argv):
    if not argv:
        return argv
    aliases = {"statys": "status", "stats": "status", "analyse": "analyze", "rec": "recommend", "recs": "recommend", "char": "chat"}
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
        cmd_scan(args.paths, args.db, args.preview, args.include_hidden, args.max_files, args.max_file_bytes)
    elif args.command == "analyze":
        cmd_analyze(args.db, args.top_terms)
    elif args.command == "recommend":
        cmd_recommend(args.db, args.top_terms)
    elif args.command == "ask":
        cmd_ask(args.query, args.db, args.limit, args.web, args.web_limit)
    elif args.command == "web":
        cmd_web(args.query, args.db, args.limit, args.depth)
    elif args.command == "crawl":
        cmd_crawl(args.urls, args.db, args.limit, args.depth, args.delay, args.cross_domain)
    elif args.command == "chat":
        cmd_chat(args.db, args.limit)
    else:
        cmd_chat(args.db, 8)
    return 0
