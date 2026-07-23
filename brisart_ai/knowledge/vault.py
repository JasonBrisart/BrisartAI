"""Knowledge Vault for BrisartAI.

The vault adds structure on top of the raw SQLite source index.

It provides:
- research collections
- local notes
- lightweight entity extraction
- source-to-topic relationships
- timeline events
- vault reports

Everything is pure Python and uses the existing BrisartAI SQLite database.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

from brisart_ai.util import now_ts, tokenize


ENTITY_RE = re.compile(
    r"\b[A-Z][A-Za-z0-9_]*(?:[ -][A-Z][A-Za-z0-9_]*){0,4}\b"
)


def init_vault_schema(index) -> None:
    """Create vault tables if they do not exist."""
    index.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS source_collections (
            source_id INTEGER NOT NULL,
            collection_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            PRIMARY KEY(source_id, collection_id),
            FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE,
            FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            collection_id INTEGER,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            entity_type TEXT NOT NULL DEFAULT 'concept',
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS source_entities (
            source_id INTEGER NOT NULL,
            entity_id INTEGER NOT NULL,
            weight INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY(source_id, entity_id),
            FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE,
            FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS timeline_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            detail TEXT NOT NULL,
            source_id INTEGER,
            event_time INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_notes_title ON notes(title);
        CREATE INDEX IF NOT EXISTS idx_notes_body ON notes(body);
        CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
        CREATE INDEX IF NOT EXISTS idx_timeline_time ON timeline_events(event_time);
        """
    )
    index.conn.commit()


def create_collection(index, name: str, description: str = "") -> str:
    """Create a research collection."""
    init_vault_schema(index)
    cleaned_name = name.strip()
    if not cleaned_name:
        return "Collection name cannot be empty."

    with index.conn:
        index.conn.execute(
            """
            INSERT OR IGNORE INTO collections(name, description, created_at)
            VALUES(?,?,?)
            """,
            (cleaned_name, description.strip(), now_ts()),
        )

    return f"Collection ready: {cleaned_name}"


def list_collections(index) -> str:
    """List all research collections."""
    init_vault_schema(index)
    rows = index.conn.execute(
        """
        SELECT collections.id, collections.name, collections.description,
               COUNT(source_collections.source_id) AS source_count
        FROM collections
        LEFT JOIN source_collections
            ON source_collections.collection_id = collections.id
        GROUP BY collections.id
        ORDER BY collections.name
        """
    ).fetchall()

    lines = ["Research Collections", ""]

    if not rows:
        lines.append("No collections exist yet.")
        lines.append("")
        lines.append("Create one with:")
        lines.append("collection create archive_research")
        return "\n".join(lines)

    for _id, name, description, count in rows:
        desc = f" - {description}" if description else ""
        lines.append(f"- {name}: {count} source(s){desc}")

    return "\n".join(lines)


def _collection_id(index, name: str) -> Optional[int]:
    row = index.conn.execute(
        "SELECT id FROM collections WHERE name=?",
        (name.strip(),),
    ).fetchone()
    if not row:
        return None
    return int(row[0])


def add_sources_to_collection(index, collection_name: str, query: str) -> str:
    """Attach matching indexed sources to a collection.

    Matching is intentionally simple and inspectable:
    - checks title
    - checks location
    - checks text
    """
    init_vault_schema(index)
    create_collection(index, collection_name)

    cid = _collection_id(index, collection_name)
    if cid is None:
        return f"Could not find collection: {collection_name}"

    terms = tokenize(query)
    if not terms:
        return "No searchable terms were provided."

    rows = index.conn.execute(
        """
        SELECT id, title, location, text
        FROM sources
        """
    ).fetchall()

    matched = []

    for source_id, title, location, text in rows:
        blob = f"{title or ''} {location or ''} {text or ''}".lower()
        if any(term in blob for term in terms):
            matched.append(source_id)

    with index.conn:
        for source_id in matched:
            index.conn.execute(
                """
                INSERT OR IGNORE INTO source_collections(
                    source_id,
                    collection_id,
                    created_at
                )
                VALUES(?,?,?)
                """,
                (source_id, cid, now_ts()),
            )

    return (
        f"Collection updated: {collection_name}\n"
        f"Matched sources added: {len(matched)}"
    )


def add_note(index, title: str, body: str, collection_name: str = "") -> str:
    """Add a local research note."""
    init_vault_schema(index)

    cid = None
    if collection_name.strip():
        create_collection(index, collection_name)
        cid = _collection_id(index, collection_name)

    cleaned_title = title.strip() or "Untitled Note"
    cleaned_body = body.strip()

    if not cleaned_body:
        return "Note body cannot be empty."

    stamp = now_ts()

    with index.conn:
        index.conn.execute(
            """
            INSERT INTO notes(title, body, collection_id, created_at, updated_at)
            VALUES(?,?,?,?,?)
            """,
            (cleaned_title, cleaned_body, cid, stamp, stamp),
        )

    return f"Note saved: {cleaned_title}"


def list_notes(index, limit: int = 20) -> str:
    """List recent notes."""
    init_vault_schema(index)

    rows = index.conn.execute(
        """
        SELECT notes.id, notes.title, notes.body, collections.name, notes.created_at
        FROM notes
        LEFT JOIN collections ON collections.id = notes.collection_id
        ORDER BY notes.created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    lines = ["Research Notes", ""]

    if not rows:
        lines.append("No notes exist yet.")
        lines.append("")
        lines.append("Add one with:")
        lines.append('note add "Title" "Body text here"')
        return "\n".join(lines)

    for note_id, title, body, collection, created_at in rows:
        preview = " ".join(body.split())[:160]
        collection_label = collection or "unassigned"
        lines.append(f"[{note_id}] {title}")
        lines.append(f"Collection: {collection_label}")
        lines.append(f"Preview: {preview}")
        lines.append("")

    return "\n".join(lines).rstrip()


def search_notes(index, query: str, limit: int = 10) -> str:
    """Search local notes."""
    init_vault_schema(index)
    terms = tokenize(query)

    if not terms:
        return "No searchable terms were provided."

    rows = index.conn.execute(
        """
        SELECT notes.id, notes.title, notes.body, collections.name
        FROM notes
        LEFT JOIN collections ON collections.id = notes.collection_id
        ORDER BY notes.updated_at DESC
        """
    ).fetchall()

    scored: List[Tuple[int, Tuple[int, str, str, Optional[str]]]] = []

    for row in rows:
        note_id, title, body, collection = row
        blob = f"{title} {body}".lower()
        score = sum(blob.count(term) for term in terms)
        if score > 0:
            scored.append((score, row))

    scored.sort(key=lambda item: item[0], reverse=True)

    lines = ["Note Search", "", f"Query: {query}", ""]

    if not scored:
        lines.append("No matching notes found.")
        return "\n".join(lines)

    for score, row in scored[:limit]:
        note_id, title, body, collection = row
        preview = " ".join(body.split())[:220]
        lines.append(f"[{note_id}] {title}")
        lines.append(f"Score: {score}")
        lines.append(f"Collection: {collection or 'unassigned'}")
        lines.append(f"Preview: {preview}")
        lines.append("")

    return "\n".join(lines).rstrip()


def extract_entities_from_text(text: str, limit: int = 30) -> List[str]:
    """Extract lightweight named entities.

    This is not machine learning. It is intentionally simple:
    - finds capitalized phrases
    - removes obvious generic phrases
    - returns stable sorted names
    """
    blocked = {
        "The",
        "This",
        "That",
        "Local",
        "Internet",
        "Optional",
        "Current",
        "Source",
        "Sources",
        "Answer",
        "Confidence",
        "Observation",
        "Suggested",
        "BrisartAI Status",
    }

    found = []

    for match in ENTITY_RE.finditer(text):
        value = " ".join(match.group(0).split())
        if value in blocked:
            continue
        if len(value) < 3:
            continue
        if value.lower() in {"python", "sqlite", "json", "html"}:
            found.append(value)
            continue
        if any(char.isupper() for char in value):
            found.append(value)

    seen = set()
    out = []

    for item in found:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)

    return out[:limit]


def rebuild_entities(index, max_sources: int = 5000) -> str:
    """Rebuild simple entity links from indexed sources."""
    init_vault_schema(index)

    rows = index.conn.execute(
        """
        SELECT id, title, text
        FROM sources
        ORDER BY indexed_at DESC
        LIMIT ?
        """,
        (max_sources,),
    ).fetchall()

    entity_count = 0
    link_count = 0

    with index.conn:
        index.conn.execute("DELETE FROM source_entities")

        for source_id, title, text in rows:
            blob = f"{title or ''}\n{text or ''}"
            entities = extract_entities_from_text(blob)

            for entity in entities:
                index.conn.execute(
                    """
                    INSERT OR IGNORE INTO entities(name, entity_type, created_at)
                    VALUES(?,?,?)
                    """,
                    (entity, "concept", now_ts()),
                )

                entity_id = index.conn.execute(
                    "SELECT id FROM entities WHERE name=?",
                    (entity,),
                ).fetchone()[0]

                index.conn.execute(
                    """
                    INSERT OR REPLACE INTO source_entities(
                        source_id,
                        entity_id,
                        weight
                    )
                    VALUES(?,?,?)
                    """,
                    (source_id, entity_id, 1),
                )

                entity_count += 1
                link_count += 1

    return (
        "Entity index rebuilt.\n"
        f"Sources reviewed: {len(rows)}\n"
        f"Entity mentions linked: {link_count}"
    )


def vault_report(index, top_entities: int = 25) -> str:
    """Return a high-level vault report."""
    init_vault_schema(index)

    total_sources = index.source_count()
    local_files = index.source_count("file")
    web_pages = index.source_count("web")

    collection_count = index.conn.execute(
        "SELECT COUNT(*) FROM collections"
    ).fetchone()[0]

    note_count = index.conn.execute(
        "SELECT COUNT(*) FROM notes"
    ).fetchone()[0]

    entity_count = index.conn.execute(
        "SELECT COUNT(*) FROM entities"
    ).fetchone()[0]

    entity_rows = index.conn.execute(
        """
        SELECT entities.name, COUNT(source_entities.source_id) AS hits
        FROM entities
        JOIN source_entities ON source_entities.entity_id = entities.id
        GROUP BY entities.id
        ORDER BY hits DESC, entities.name ASC
        LIMIT ?
        """,
        (top_entities,),
    ).fetchall()

    collection_rows = index.conn.execute(
        """
        SELECT collections.name, COUNT(source_collections.source_id) AS hits
        FROM collections
        LEFT JOIN source_collections
            ON source_collections.collection_id = collections.id
        GROUP BY collections.id
        ORDER BY hits DESC, collections.name ASC
        """
    ).fetchall()

    lines = []
    lines.append("BrisartAI Knowledge Vault")
    lines.append("")
    lines.append("Vault Summary")
    lines.append("-------------")
    lines.append(f"Indexed sources: {total_sources}")
    lines.append(f"Local files: {local_files}")
    lines.append(f"Web pages: {web_pages}")
    lines.append(f"Collections: {collection_count}")
    lines.append(f"Notes: {note_count}")
    lines.append(f"Known entities: {entity_count}")
    lines.append("")

    if collection_rows:
        lines.append("Collections")
        lines.append("-----------")
        for name, hits in collection_rows:
            lines.append(f"- {name}: {hits} source(s)")
        lines.append("")

    if entity_rows:
        lines.append("Top Entities")
        lines.append("------------")
        for name, hits in entity_rows:
            lines.append(f"- {name}: {hits} source link(s)")
        lines.append("")
    else:
        lines.append("Top Entities")
        lines.append("------------")
        lines.append("No entities have been built yet.")
        lines.append("Run:")
        lines.append("vault rebuild")
        lines.append("")

    lines.append("Interpretation")
    lines.append("--------------")
    if total_sources == 0:
        lines.append(
            "The vault is ready, but no files or web pages have been indexed yet."
        )
    else:
        lines.append(
            "The vault has indexed material available. Collections, notes, "
            "and entity links can now turn the raw index into organized research."
        )

    lines.append("")
    lines.append("Suggested next move: create a collection, add notes, or run vault rebuild.")

    return "\n".join(lines)


def timeline(index, query: str, limit: int = 30) -> str:
    """Build a simple timeline around a term or concept."""
    init_vault_schema(index)
    terms = tokenize(query)

    if not terms:
        return "No searchable timeline term was provided."

    rows = index.conn.execute(
        """
        SELECT id, source_type, title, location, text, indexed_at
        FROM sources
        ORDER BY indexed_at ASC
        """
    ).fetchall()

    matches = []

    for source_id, source_type, title, location, text, indexed_at in rows:
        blob = f"{title or ''} {location or ''} {text or ''}".lower()
        score = sum(blob.count(term) for term in terms)
        if score > 0:
            matches.append((indexed_at, score, source_id, source_type, title, location))

    matches.sort(key=lambda item: (item[0], -item[1]))

    lines = []
    lines.append("Timeline")
    lines.append("--------")
    lines.append(f"Topic: {query}")
    lines.append("")

    if not matches:
        lines.append("No matching indexed sources found.")
        return "\n".join(lines)

    for indexed_at, score, source_id, source_type, title, location in matches[:limit]:
        label = title or location
        lines.append(f"- Indexed at: {indexed_at}")
        lines.append(f"  Source: {source_type}: {label}")
        lines.append(f"  Match score: {score}")
        lines.append(f"  Location: {location}")
        lines.append("")

    if len(matches) > limit:
        lines.append(f"... {len(matches) - limit} additional matching sources not shown.")

    return "\n".join(lines).rstrip()