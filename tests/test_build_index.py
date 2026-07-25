"""build_index: flattening, content extraction, and the FTS index itself."""
from __future__ import annotations

import json
import sqlite3

from conftest import ROOT_PARENT, make_conv, make_msg, search_corpus

from build_index import (
    _attachment_names,
    _attachment_text,
    _join_blocks,
    _tool_content,
    _tool_names,
    build,
    flatten,
)
from samples.build_samples import CLAUDE_CONVERSATIONS


def test_flatten_seq_and_parent_default():
    conv = make_conv("c-1", "T", [
        make_msg("m-1", "human", body="hi"),            # no parent field at all
        make_msg("m-2", "assistant", "m-1", body="yo"),
    ])
    rows = flatten(conv)
    assert [r.seq for r in rows] == [0, 1]
    assert rows[0].parent_message_uuid == ROOT_PARENT
    assert rows[1].parent_message_uuid == "m-1"


def test_flatten_body_falls_back_to_text_field():
    conv = make_conv("c-1", "T", [make_msg("m-1", "human", content=[], text="fallback")])
    assert flatten(conv)[0].body == "fallback"


def test_join_blocks_skips_empty_and_joins():
    content = [{"type": "text", "text": "a"}, {"type": "text", "text": ""},
               {"type": "thinking", "text": "t"}, {"type": "text", "text": "b"}]
    assert _join_blocks(content, "text") == "a\n\nb"
    assert _join_blocks(content, "thinking") == "t"


def test_tool_names_dedupes_preserving_order():
    content = [{"type": "tool_use", "name": "web_search"},
               {"type": "tool_use", "name": "artifacts"},
               {"type": "tool_use", "name": "web_search"},
               {"type": "tool_use"}]
    assert _tool_names(content) == "web_search, artifacts"


def test_attachment_names_merges_without_duplicates():
    m = {"attachments": [{"file_name": "a.txt"}], "files": [{"file_name": "a.txt"},
                                                            {"file_name": "b.pdf"}]}
    assert _attachment_names(m) == "a.txt, b.pdf"


def test_attachment_text_and_tool_content():
    m = {"attachments": [{"file_name": "a.txt", "extracted_content": "alpha"},
                         {"file_name": "b.txt"}]}
    assert _attachment_text(m) == "alpha"
    assert _attachment_text({}) == ""
    content = [
        {"type": "tool_use", "name": "artifacts",
         "input": {"title": "Art", "content": "art-body"}},
        {"type": "tool_use", "name": "artifacts", "input": {"new_str": "patched"}},
        {"type": "tool_use", "name": "create_file",
         "input": {"path": "notes/x.md", "file_text": "file-body"}},
        {"type": "tool_use", "name": "web_search", "input": {"query": "ignored"}},
    ]
    out = _tool_content(content)
    assert "Art\nart-body" in out and "patched" in out and "notes/x.md\nfile-body" in out
    assert "ignored" not in out


def build_db(tmp_path, conversations):
    src = tmp_path / "conversations.json"
    src.write_text(json.dumps(conversations))
    db_path = tmp_path / "conversations.db"
    build(src, db_path)
    return sqlite3.connect(db_path)

def test_build_indexes_sample_export(tmp_path):
    db = build_db(tmp_path, CLAUDE_CONVERSATIONS)
    n_conv = db.execute("SELECT count(*) FROM conversations").fetchone()[0]
    assert n_conv == len(CLAUDE_CONVERSATIONS)
    # One title row (message_uuid NULL) per named conversation.
    n_titles = db.execute(
        "SELECT count(*) FROM search WHERE message_uuid IS NULL").fetchone()[0]
    assert n_titles == n_conv


def test_fts_covers_artifacts_and_attachments(tmp_path):
    db = build_db(tmp_path, search_corpus())
    def uuids(q):
        return {r[0] for r in db.execute(
            "SELECT conversation_uuid FROM search WHERE search MATCH ?", (q,))}
    # Artifact body content is searchable (issue #11).
    assert uuids('"zorblatt"') == {"cccccccc-0000-4000-8000-000000000003"}
    # Attachment extracted text is searchable (issue #11).
    assert uuids('"quuxfoo"') == {"cccccccc-0000-4000-8000-000000000003"}
    # A title term matches exactly one row for that conversation (issue #12).
    rows = db.execute(
        """SELECT message_uuid FROM search
           WHERE search MATCH '"antitrust"' AND conversation_uuid = ?""",
        ("aaaaaaaa-0000-4000-8000-000000000001",)).fetchall()
    assert rows == [(None,)]
