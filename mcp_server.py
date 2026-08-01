"""MCP server exposing a Chronicle archive as live, queryable memory.

Serves conversations.db (build it first: python build_index.py) over stdio.
Nothing is uploaded anywhere — clients query the database on your machine.

Run:      python mcp_server.py [path/to/conversations.db]
Install:  pip install ".[mcp]"

Claude Desktop / Claude Code config:

    {
      "mcpServers": {
        "chronicle": {
          "command": "python",
          "args": ["/path/to/chronicle/mcp_server.py",
                   "/path/to/chronicle/conversations.db"]
        }
      }
    }
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

from mcp.server import MCPServer

import store

DB_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "conversations.db"
mcp = MCPServer(
    "chronicle",
    instructions="Searchable archive of the user's past AI conversations "
    "(a Claude or ChatGPT history export). Use `search` to find relevant "
    "conversations, then `get_conversation` to read one.",
)
_local = threading.local()


def db():
    """One read-only connection per thread.

    MCPServer runs these sync tools on anyio worker threads, and concurrent calls
    land on different ones. A single shared connection doesn't work: sqlite3 binds
    a connection to its creating thread, and even with check_same_thread=False the
    per-connection statement cache lets two threads running the same SQL consume
    each other's rows.
    """
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _local.conn = store.connect(DB_PATH)
    return conn


@mcp.tool()
def search(query: str, limit: int = 20) -> str:
    """Full-text search across all messages, thinking, attachments, and
    artifact content. Returns ranked conversations with hit counts and a
    snippet ([] marks the match)."""
    return json.dumps(store.search(db(), query, limit), ensure_ascii=False, indent=1)


@mcp.tool()
def list_conversations(limit: int = 50, since: str = "", sort: str = "updated") -> str:
    """List conversations (sort: updated | created | name; since: ISO date
    filters on updated_at)."""
    return json.dumps(
        store.list_conversations(db(), limit, since, sort), ensure_ascii=False, indent=1
    )


@mcp.tool()
def get_conversation(uuid: str, include_thinking: bool = False) -> str:
    """A full conversation as a Markdown transcript."""
    md = store.conversation_markdown(db(), uuid, include_thinking)
    return md if md is not None else f"No conversation with uuid {uuid}."


@mcp.tool()
def list_artifacts(query: str = "", limit: int = 50) -> str:
    """Artifacts and files the assistant created, newest first; `query`
    filters by title/type/content. Returns keys for get_artifact."""
    return json.dumps(store.list_artifacts(db(), query, limit), ensure_ascii=False, indent=1)


@mcp.tool()
def get_artifact(key: str) -> str:
    """Full content of one artifact/created file (key from list_artifacts)."""
    a = store.get_artifact(db(), key)
    if a is None:
        return f"No artifact with key {key}."
    header = f"# {a['title']}\n_{a['kind']} | {a['type'] or 'text'} | v{a['versions']}_\n\n"
    return header + a["text"]


@mcp.tool()
def stats() -> str:
    """Archive totals: conversations, messages, artifacts, date range."""
    return json.dumps(store.stats(db()), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    try:
        # Probe now, so a missing index fails here instead of inside a tool call.
        # Discarded: each worker thread opens its own connection via db().
        store.connect(DB_PATH).close()
    except FileNotFoundError as e:
        sys.exit(f"chronicle: {e}")
    mcp.run()
