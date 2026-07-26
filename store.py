"""Read-only query layer over conversations.db (built by build_index.py).

Stdlib-only, so consumers that can't or shouldn't import Flask/MCP (tests,
scripts) can use the same queries. The MCP server (mcp_server.py) is a thin
wrapper over these functions.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def connect(db_path: Path | str) -> sqlite3.Connection:
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} not found. Run: python build_index.py")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def fts_query(raw: str) -> str:
    """Turn a user string into a safe FTS5 MATCH query (prefix on last token)."""
    tokens = [t for t in raw.replace('"', " ").split() if t]
    if not tokens:
        return ""
    quoted = [f'"{t}"' for t in tokens[:-1]]
    quoted.append(f'"{tokens[-1]}"*')
    return " ".join(quoted)


def search(db: sqlite3.Connection, query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Ranked conversations matching `query`: exact hit counts, separate
    title-match flag, one snippet each (same scheme as app.py /api/search)."""
    match = fts_query(query)
    if not match:
        return []
    grouped: dict[str, dict[str, Any]] = {}
    for r in db.execute(
        """SELECT conversation_uuid AS uuid,
                  SUM(message_uuid IS NOT NULL) AS hits,
                  MAX(message_uuid IS NULL) AS title_match
           FROM search WHERE search MATCH ? GROUP BY conversation_uuid""",
        (match,),
    ):
        grouped[r["uuid"]] = {"uuid": r["uuid"], "hits": r["hits"],
                              "title_match": bool(r["title_match"]), "snippet": None}
    if not grouped:
        return []
    for r in db.execute(
        """SELECT conversation_uuid AS uuid,
                  snippet(search, 3, '[', ']', ' … ', 12) AS snippet
           FROM search WHERE search MATCH ? AND message_uuid IS NOT NULL
           ORDER BY rank LIMIT 2000""",
        (match,),
    ):
        g = grouped.get(r["uuid"])
        if g is not None and g["snippet"] is None:
            g["snippet"] = r["snippet"]
    placeholders = ",".join("?" * len(grouped))
    for m in db.execute(
        f"""SELECT uuid, name, updated_at, message_count
            FROM conversations WHERE uuid IN ({placeholders})""",
        tuple(grouped),
    ):
        grouped[m["uuid"]].update(
            name=m["name"], updated_at=m["updated_at"], message_count=m["message_count"]
        )
    results = sorted(
        grouped.values(),
        key=lambda d: (d["hits"], d["title_match"], d.get("updated_at") or ""),
        reverse=True,
    )
    return results[:limit]


def list_conversations(
    db: sqlite3.Connection, limit: int = 50, since: str = "", sort: str = "updated"
) -> list[dict[str, Any]]:
    order = {"updated": "updated_at DESC", "created": "created_at ASC",
             "name": "name ASC"}.get(sort, "updated_at DESC")
    rows = db.execute(
        f"""SELECT uuid, name, created_at, updated_at, message_count
            FROM conversations WHERE updated_at >= ? ORDER BY {order} LIMIT ?""",
        (since or "", limit),
    ).fetchall()
    return [dict(r) for r in rows]


def conversation_markdown(db: sqlite3.Connection, uuid: str,
                          include_thinking: bool = False) -> str | None:
    """A conversation as a compact Markdown transcript, or None if unknown."""
    conv = db.execute("SELECT * FROM conversations WHERE uuid = ?", (uuid,)).fetchone()
    if conv is None:
        return None
    lines = [f"# {conv['name']}",
             f"_{(conv['created_at'] or '')[:16]} -> {(conv['updated_at'] or '')[:16]}"
             f" | {conv['message_count']} messages | uuid {uuid}_"]
    for m in db.execute(
        """SELECT sender, seq, created_at, body, thinking, tools, attachments
           FROM messages WHERE conversation_uuid = ? ORDER BY seq""",
        (uuid,),
    ):
        speaker = "You" if m["sender"] == "human" else "Assistant"
        lines.append(f"\n## [{m['seq']}] {speaker}")
        if m["attachments"]:
            lines.append(f"_[attachments: {m['attachments']}]_")
        if m["body"]:
            lines.append(m["body"])
        if include_thinking and m["thinking"]:
            lines.append(f"_[thinking]_\n{m['thinking']}")
        if m["tools"]:
            lines.append(f"_[tools used: {m['tools']}]_")
    return "\n\n".join(lines) + "\n"


def list_artifacts(db: sqlite3.Connection, query: str = "",
                   limit: int = 50) -> list[dict[str, Any]]:
    """Artifacts/created files, newest first; `query` filters title/type/text."""
    like = f"%{query}%"
    rows = db.execute(
        """SELECT a.key, a.kind, a.title, a.type, a.versions, a.updated_at,
                  a.conversation_uuid, c.name AS conversation_name,
                  length(a.text) AS size
           FROM artifacts a LEFT JOIN conversations c ON c.uuid = a.conversation_uuid
           WHERE ? = '' OR a.title LIKE ? OR a.type LIKE ? OR a.text LIKE ?
           ORDER BY a.updated_at DESC LIMIT ?""",
        (query, like, like, like, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_artifact(db: sqlite3.Connection, key: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM artifacts WHERE key = ?", (key,)).fetchone()
    return dict(row) if row else None


def stats(db: sqlite3.Connection) -> dict[str, Any]:
    row = db.execute(
        """SELECT COUNT(*) AS conversations, SUM(message_count) AS messages,
                  MIN(created_at) AS earliest, MAX(updated_at) AS latest
           FROM conversations"""
    ).fetchone()
    out = dict(row)
    out["artifacts"] = db.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
    return out
