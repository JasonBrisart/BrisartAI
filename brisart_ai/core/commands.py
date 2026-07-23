"""BrisartAI command handlers.

Each handler opens an Index, does one job, prints its result, and
guarantees the connection is closed. Handlers are intentionally thin;
the real logic lives in the knowledge, scanning, and web modules.
"""
from __future__ import annotations

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
