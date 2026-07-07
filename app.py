"""Local web UI for browsing and searching a Claude conversations export.

Run: python app.py   (then open http://127.0.0.1:5000)
Requires conversations.db (build it with: python build_index.py).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

DB_PATH = Path(__file__).parent / "conversations.db"
ROOT_PARENT = "00000000-0000-4000-8000-000000000000"

app = Flask(__name__)
# Re-render templates when the file changes so edits don't require a restart.
app.config["TEMPLATES_AUTO_RELOAD"] = True

# The DB is read-only after build_index, so one shared read-only connection
# serves every request — no per-request connect/close churn.
_db: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
    global _db
    if _db is None:
        if not DB_PATH.exists():
            raise RuntimeError(
                f"{DB_PATH.name} not found. Run: python build_index.py"
            )
        _db = sqlite3.connect(
            f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False
        )
        _db.row_factory = sqlite3.Row
    return _db


def _fts_query(raw: str) -> str:
    """Turn a user string into a safe FTS5 MATCH query (prefix on last token)."""
    tokens = [t for t in raw.replace('"', " ").split() if t]
    if not tokens:
        return ""
    quoted = [f'"{t}"' for t in tokens[:-1]]
    quoted.append(f'"{tokens[-1]}"*')
    return " ".join(quoted)


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/api/conversations")
def list_conversations() -> Any:
    db = get_db()
    sort = request.args.get("sort", "updated")
    order_col = {"updated": "updated_at", "created": "created_at", "name": "name"}.get(
        sort, "updated_at"
    )
    direction = "ASC" if sort == "name" else "DESC"
    rows = db.execute(
        f"""SELECT uuid, name, created_at, updated_at, message_count
            FROM conversations ORDER BY {order_col} {direction}"""
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/search")
def search() -> Any:
    db = get_db()
    raw = request.args.get("q", "").strip()
    match = _fts_query(raw)
    if not match:
        return jsonify({"query": raw, "conversations": []})

    # snippet()/rank are FTS5 auxiliary functions: they only work on a query
    # that scans the FTS table directly (no JOIN). So query search alone, fold
    # to one row per conversation, then attach conversation metadata.
    rows = db.execute(
        """
        SELECT conversation_uuid AS uuid,
               snippet(search, 3, '<<<', '>>>', ' … ', 12) AS snippet
        FROM search
        WHERE search MATCH ?
        ORDER BY rank
        LIMIT 2000
        """,
        (match,),
    ).fetchall()

    grouped: dict[str, dict[str, Any]] = {}
    for r in rows:
        g_row = grouped.get(r["uuid"])
        if g_row is None:
            grouped[r["uuid"]] = {"uuid": r["uuid"], "snippet": r["snippet"], "hits": 1}
        else:
            g_row["hits"] += 1

    if not grouped:
        return jsonify({"query": raw, "conversations": []})

    placeholders = ",".join("?" * len(grouped))
    meta = {
        m["uuid"]: m
        for m in db.execute(
            f"""SELECT uuid, name, updated_at, message_count
                FROM conversations WHERE uuid IN ({placeholders})""",
            tuple(grouped),
        ).fetchall()
    }
    for uuid, row in grouped.items():
        m = meta.get(uuid)
        if m is not None:
            row["name"] = m["name"]
            row["updated_at"] = m["updated_at"]
            row["message_count"] = m["message_count"]

    results = sorted(
        grouped.values(),
        key=lambda d: (d["hits"], d.get("updated_at") or ""),
        reverse=True,
    )
    return jsonify({"query": raw, "conversations": results[:200]})


def _build_thread(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reconstruct the reply tree from parent_message_uuid.

    Returns root-level nodes; each node has a 'children' list. Most
    conversations are linear, but branched ones nest correctly.
    """
    by_uuid = {m["uuid"]: {**m, "children": []} for m in messages}
    roots: list[dict[str, Any]] = []
    for m in messages:
        node = by_uuid[m["uuid"]]
        parent = by_uuid.get(m["parent_message_uuid"])
        if parent is None or m["parent_message_uuid"] == ROOT_PARENT:
            roots.append(node)
        else:
            parent["children"].append(node)
    return roots


@app.route("/api/conversation/<uuid>")
def conversation(uuid: str) -> Any:
    db = get_db()
    conv = db.execute(
        "SELECT * FROM conversations WHERE uuid = ?", (uuid,)
    ).fetchone()
    if conv is None:
        return jsonify({"error": "not found"}), 404
    messages = [
        dict(r)
        for r in db.execute(
            """SELECT uuid, sender, seq, parent_message_uuid, created_at,
                      body, thinking, tools, attachments
               FROM messages WHERE conversation_uuid = ? ORDER BY seq""",
            (uuid,),
        ).fetchall()
    ]
    branched = len({m["parent_message_uuid"] for m in messages}) < len(messages)
    return jsonify(
        {
            "conversation": dict(conv),
            "thread": _build_thread(messages),
            "branched": branched,
        }
    )


@app.route("/api/stats")
def stats() -> Any:
    db = get_db()
    row = db.execute(
        """SELECT COUNT(*) AS conversations,
                  SUM(message_count) AS messages,
                  MIN(created_at) AS earliest,
                  MAX(updated_at) AS latest
           FROM conversations"""
    ).fetchone()
    return jsonify(dict(row))


if __name__ == "__main__":
    # Port 5000 is taken by macOS AirPlay Receiver/ControlCenter; default to 5050.
    port = int(os.environ.get("PORT", "5050"))
    app.run(host="127.0.0.1", port=port, debug=False)
