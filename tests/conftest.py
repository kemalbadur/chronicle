"""Shared factories/fixtures: tiny synthetic Claude-export structures.

The realistic sample data in samples/build_samples.py is used for shape tests;
the factories here build minimal conversations with unique tokens for search
tests, where sample content would overlap between bodies and artifacts.
"""
from __future__ import annotations

ROOT_PARENT = "00000000-0000-4000-8000-000000000000"


def make_msg(uuid, sender, parent=None, body="", content=None, **extra):
    m = {
        "uuid": uuid,
        "text": "",
        "content": content if content is not None
        else ([{"type": "text", "text": body}] if body else []),
        "sender": sender,
        "created_at": "2026-05-01T10:00:00Z",
        "attachments": [],
        "files": [],
    }
    if parent is not None:
        m["parent_message_uuid"] = parent
    m.update(extra)
    return m


def make_conv(uuid, name, messages, **extra):
    c = {
        "uuid": uuid,
        "name": name,
        "summary": "",
        "created_at": "2026-05-01T10:00:00Z",
        "updated_at": "2026-05-02T10:00:00Z",
        "chat_messages": messages,
    }
    c.update(extra)
    return c


def search_corpus():
    """Three conversations exercising title / body / artifact / attachment matches."""
    artifact = {
        "type": "tool_use",
        "name": "artifacts",
        "input": {"id": "art-1", "type": "text/html", "title": "Zorblatt dashboard",
                  "command": "create", "content": "<html>the zorblatt metrics</html>"},
    }
    attachment = {"file_name": "notes.txt", "file_type": "txt",
                  "extracted_content": "quuxfoo appears only in this upload"}
    return [
        make_conv(
            "aaaaaaaa-0000-4000-8000-000000000001", "Antitrust Deep Dive",
            [
                make_msg("ma-1", "human", ROOT_PARENT, "hello world"),
                make_msg("ma-2", "assistant", "ma-1", "nothing relevant here"),
            ],
            updated_at="2026-05-01T10:00:00Z",
        ),
        make_conv(
            "bbbbbbbb-0000-4000-8000-000000000002", "Weekly notes",
            [
                make_msg("mb-1", "human", ROOT_PARENT,
                         "let's discuss antitrust policy and antitrust law"),
            ],
            updated_at="2026-05-02T10:00:00Z",
        ),
        make_conv(
            "cccccccc-0000-4000-8000-000000000003", "Dashboard build",
            [
                make_msg("mc-1", "human", ROOT_PARENT, "make me a dashboard"),
                make_msg("mc-2", "assistant", "mc-1", "here you go",
                         content=[{"type": "text", "text": "here you go"}, artifact]),
                make_msg("mc-3", "human", "mc-2", "and here are my notes",
                         attachments=[attachment]),
            ],
            updated_at="2026-05-03T10:00:00Z",
        ),
    ]
