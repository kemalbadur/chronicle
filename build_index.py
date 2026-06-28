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
            )
        )
    return rows


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
    for conv in data:
        messages = flatten(conv)
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
        name = conv.get("name") or ""
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
            searchable = "\n".join(p for p in (m.body, m.thinking, m.attachments) if p)
            if searchable.strip():
                search_rows.append((m.uuid, m.conversation_uuid, name, searchable))

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
