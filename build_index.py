"""Build a searchable SQLite index from a Claude conversations.json export.

Parses the export once and writes conversations.db with:
  - conversations: one row per conversation
  - messages: one row per message, with flattened text / thinking / tool info
  - search: FTS5 virtual table over message + conversation text

Run: python build_index.py [conversations.json] [conversations.db]
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_PARENT = "00000000-0000-4000-8000-000000000000"


@dataclass
class FlatMessage:
    uuid: str
    conversation_uuid: str
    sender: str
    seq: int
    parent_message_uuid: str
    created_at: str
    body: str
    thinking: str
    tools: str
    attachments: str
    search_extra: str  # attachment extracted text + artifact/created-file content


def _join_blocks(content: list[dict[str, Any]], block_type: str) -> str:
    parts: list[str] = []
    for block in content:
        if block.get("type") == block_type and block.get("text"):
            parts.append(block["text"])
    return "\n\n".join(parts)


def _tool_names(content: list[dict[str, Any]]) -> str:
    names: list[str] = []
    for block in content:
        if block.get("type") == "tool_use" and block.get("name"):
            names.append(block["name"])
    return ", ".join(dict.fromkeys(names))


def _attachment_names(message: dict[str, Any]) -> str:
    names: list[str] = []
    for att in message.get("attachments") or []:
        if att.get("file_name"):
            names.append(att["file_name"])
    for f in message.get("files") or []:
        if f.get("file_name") and f["file_name"] not in names:
            names.append(f["file_name"])
    return ", ".join(names)


def _attachment_text(message: dict[str, Any]) -> str:
    """Extracted text of uploaded attachments (files[] carry no content)."""
    parts: list[str] = []
    for att in message.get("attachments") or []:
        if att.get("extracted_content"):
            parts.append(att["extracted_content"])
    return "\n\n".join(parts)


def _tool_content(content: list[dict[str, Any]]) -> str:
    """Text of artifacts and Claude-created files, for the search index."""
    parts: list[str] = []
    for block in content:
        if block.get("type") != "tool_use":
            continue
        inp = block.get("input") or {}
        if block.get("name") == "artifacts":
            text = inp.get("content") or inp.get("new_str") or ""
            title = inp.get("title") or ""
        elif block.get("name") == "create_file":
            text = inp.get("file_text") or ""
            title = inp.get("path") or ""
        else:
            continue
        if text:
            parts.append("\n".join(p for p in (title, text) if p))
    return "\n\n".join(parts)


def flatten(conversation: dict[str, Any]) -> list[FlatMessage]:
    rows: list[FlatMessage] = []
    for seq, msg in enumerate(conversation.get("chat_messages", [])):
        content = msg.get("content") or []
        body = _join_blocks(content, "text") or (msg.get("text") or "")
        rows.append(
            FlatMessage(
                uuid=msg["uuid"],
                conversation_uuid=conversation["uuid"],
                sender=msg.get("sender", ""),
                seq=seq,
                parent_message_uuid=msg.get("parent_message_uuid") or ROOT_PARENT,
                created_at=msg.get("created_at") or "",
                body=body,
                thinking=_join_blocks(content, "thinking"),
                tools=_tool_names(content),
                attachments=_attachment_names(msg),
                search_extra="\n\n".join(
                    p for p in (_attachment_text(msg), _tool_content(content)) if p
                ),
            )
        )
    return rows


def collect_artifacts(conv: dict[str, Any]) -> list[tuple]:
    """Rows for the artifacts table: artifacts (deduped by id, keeping the
    latest full-content version) and Claude-created files (deduped by path),
    mirroring the standalone viewer's indexArtifacts()."""
    entries: dict[str, dict[str, Any]] = {}
    for msg in conv.get("chat_messages", []):
        when = msg.get("created_at") or ""
        for block in msg.get("content") or []:
            if block.get("type") != "tool_use":
                continue
            inp = block.get("input") or {}
            if block.get("name") == "artifacts":
                text = inp.get("content") or inp.get("new_str") or ""
                if not text:
                    continue
                full = bool(inp.get("content"))
                key = f"{conv['uuid']}|art|{inp.get('id') or inp.get('title') or ''}"
                e = entries.get(key)
                if e is None:
                    entries[key] = {
                        "key": key, "kind": "artifact",
                        "title": inp.get("title") or "Artifact",
                        "type": inp.get("type") or "", "text": text,
                        "created_at": when, "updated_at": when,
                        "versions": 1, "_full": full,
                    }
                else:
                    e["versions"] += 1
                    e["updated_at"] = when or e["updated_at"]
                    e["title"] = inp.get("title") or e["title"]
                    e["type"] = inp.get("type") or e["type"]
                    if full or not e["_full"]:
                        e["text"] = text
                        e["_full"] = e["_full"] or full
            elif block.get("name") == "create_file" and inp.get("file_text"):
                path = inp.get("path") or "file"
                key = f"{conv['uuid']}|file|{path}"
                e = entries.get(key)
                if e is None:
                    entries[key] = {
                        "key": key, "kind": "file",
                        "title": path.rsplit("/", 1)[-1], "type": "",
                        "text": inp["file_text"], "created_at": when,
                        "updated_at": when, "versions": 1, "_full": True,
                    }
                else:
                    e["versions"] += 1
                    e["updated_at"] = when or e["updated_at"]
                    e["text"] = inp["file_text"]
    return [
        (e["key"], conv["uuid"], e["kind"], e["title"], e["type"], e["text"],
         e["created_at"], e["updated_at"], e["versions"])
        for e in entries.values()
    ]


SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE conversations (
    uuid TEXT PRIMARY KEY,
    name TEXT,
    summary TEXT,
    created_at TEXT,
    updated_at TEXT,
    message_count INTEGER
);

-- Back the sidebar sorts (updated / created / name) so they don't scan + sort.
CREATE INDEX idx_conv_updated ON conversations(updated_at);
CREATE INDEX idx_conv_created ON conversations(created_at);
CREATE INDEX idx_conv_name ON conversations(name);

CREATE TABLE messages (
    uuid TEXT PRIMARY KEY,
    conversation_uuid TEXT,
    sender TEXT,
    seq INTEGER,
    parent_message_uuid TEXT,
    created_at TEXT,
    body TEXT,
    thinking TEXT,
    tools TEXT,
    attachments TEXT
);

CREATE INDEX idx_messages_conv ON messages(conversation_uuid, seq);

-- Artifacts / Claude-created files, one row per (conversation, artifact),
-- latest full version kept. Consumed by the MCP server and future tools.
CREATE TABLE artifacts (
    key TEXT PRIMARY KEY,
    conversation_uuid TEXT,
    kind TEXT,
    title TEXT,
    type TEXT,
    text TEXT,
    created_at TEXT,
    updated_at TEXT,
    versions INTEGER
);

CREATE INDEX idx_artifacts_conv ON artifacts(conversation_uuid);

CREATE VIRTUAL TABLE search USING fts5(
    message_uuid UNINDEXED,
    conversation_uuid UNINDEXED,
    name,
    body,
    tokenize = 'porter unicode61'
);
"""


def build(src: Path, db_path: Path) -> None:
    start = time.time()
    print(f"Loading {src} ...")
    data = json.loads(src.read_text())
    print(f"  {len(data)} conversations loaded in {time.time() - start:.1f}s")

    if db_path.exists():
        db_path.unlink()
    for suffix in ("-wal", "-shm"):
        side = db_path.with_name(db_path.name + suffix)
        if side.exists():
            side.unlink()

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    conv_rows = []
    msg_rows = []
    search_rows = []
    artifact_rows = []
    for conv in data:
        messages = flatten(conv)
        artifact_rows.extend(collect_artifacts(conv))
        conv_rows.append(
            (
                conv["uuid"],
                conv.get("name") or "(untitled)",
                conv.get("summary") or "",
                conv.get("created_at") or "",
                conv.get("updated_at") or "",
                len(messages),
            )
        )
        # One title row per conversation (message_uuid NULL): a term that
        # matches the title scores once, not once per message (issue #12).
        name = conv.get("name") or ""
        if name:
            search_rows.append((None, conv["uuid"], name, ""))
        for m in messages:
            msg_rows.append(
                (
                    m.uuid,
                    m.conversation_uuid,
                    m.sender,
                    m.seq,
                    m.parent_message_uuid,
                    m.created_at,
                    m.body,
                    m.thinking,
                    m.tools,
                    m.attachments,
                )
            )
            searchable = "\n".join(
                p for p in (m.body, m.thinking, m.attachments, m.search_extra) if p
            )
            if searchable.strip():
                search_rows.append((m.uuid, m.conversation_uuid, "", searchable))

    conn.executemany(
        "INSERT INTO conversations VALUES (?,?,?,?,?,?)", conv_rows
    )
    conn.executemany(
        "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?)", msg_rows
    )
    conn.executemany(
        "INSERT INTO search (message_uuid, conversation_uuid, name, body) VALUES (?,?,?,?)",
        search_rows,
    )
    conn.executemany(
        "INSERT INTO artifacts VALUES (?,?,?,?,?,?,?,?,?)", artifact_rows
    )
    conn.commit()
    conn.execute("INSERT INTO search(search) VALUES('optimize')")
    conn.commit()
    conn.close()

    print(
        f"  {len(msg_rows)} messages, {len(search_rows)} indexed "
        f"-> {db_path} in {time.time() - start:.1f}s total"
    )


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("conversations.json")
    db_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("conversations.db")
    if not src.exists():
        sys.exit(f"Source not found: {src}")
    build(src, db_path)


if __name__ == "__main__":
    main()
