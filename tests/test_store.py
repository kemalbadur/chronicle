"""store.py query layer + the artifacts table, over a freshly built index."""
from __future__ import annotations

import asyncio
import json

import pytest
from conftest import search_corpus

import store
from build_index import build, collect_artifacts
from samples.build_samples import CLAUDE_CONVERSATIONS


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("store")
    src = tmp / "conversations.json"
    src.write_text(json.dumps(search_corpus() + CLAUDE_CONVERSATIONS))
    build(src, tmp / "conversations.db")
    return store.connect(tmp / "conversations.db")


def test_collect_artifacts_dedupes_versions():
    conv = {
        "uuid": "c-1",
        "chat_messages": [
            {"created_at": "2026-01-01T00:00:00Z", "content": [
                {"type": "tool_use", "name": "artifacts",
                 "input": {"id": "a1", "type": "text/html", "title": "Page",
                           "command": "create", "content": "v1 full"}}]},
            {"created_at": "2026-01-02T00:00:00Z", "content": [
                {"type": "tool_use", "name": "artifacts",
                 "input": {"id": "a1", "command": "update", "new_str": "patch"}},
                {"type": "tool_use", "name": "create_file",
                 "input": {"path": "out/report.md", "file_text": "hello"}}]},
        ],
    }
    rows = collect_artifacts(conv)
    by_kind = {r[2]: r for r in rows}
    art = by_kind["artifact"]
    assert art[3] == "Page" and art[8] == 2        # title, versions
    assert art[5] == "v1 full"                     # full version kept over patch
    assert art[7] == "2026-01-02T00:00:00Z"        # updated_at advanced
    assert by_kind["file"][3] == "report.md"


def test_search_ranks_and_flags_titles(db):
    results = store.search(db, "antitrust")
    assert results[0]["name"] == "Weekly notes" and results[0]["hits"] == 1
    assert results[1]["name"] == "Antitrust Deep Dive"
    assert results[1]["title_match"] is True and results[1]["hits"] == 0
    assert store.search(db, "") == []
    assert store.search(db, "zorblatt")[0]["name"] == "Dashboard build"


def test_list_conversations_since_and_sort(db):
    all_rows = store.list_conversations(db, sort="name")
    names = [r["name"] for r in all_rows]
    assert names == sorted(names)
    recent = store.list_conversations(db, since="2026-05-03")
    assert {r["name"] for r in recent} >= {"Dashboard build"}
    assert all(r["updated_at"] >= "2026-05-03" for r in recent)


def test_conversation_markdown(db):
    uuid = "22222222-2222-4222-8222-222222222222"  # sample artifact chat
    md = store.conversation_markdown(db, uuid)
    assert md.startswith("# Chicago Pile-1")
    assert "## [0] You" in md and "## [1] Assistant" in md
    assert "_[thinking]_" not in md
    assert "_[thinking]_" in store.conversation_markdown(
        db, "11111111-1111-4111-8111-111111111111", include_thinking=True)
    assert store.conversation_markdown(db, "nope") is None


def test_artifacts_listing_and_get(db):
    arts = store.list_artifacts(db)
    assert {a["title"] for a in arts} >= {
        "Zorblatt dashboard", "UChicago milestones timeline", "Maroons crest"}
    hit = store.list_artifacts(db, query="zorblatt")
    assert len(hit) == 1 and hit[0]["conversation_name"] == "Dashboard build"
    art = store.get_artifact(db, hit[0]["key"])
    assert "zorblatt metrics" in art["text"]
    assert store.get_artifact(db, "nope") is None


def test_stats(db):
    s = store.stats(db)
    assert s["conversations"] == 6 and s["artifacts"] == 3


def test_mcp_server_registers_tools(tmp_path, monkeypatch):
    pytest.importorskip("mcp")
    import mcp_server
    tools = asyncio.run(mcp_server.mcp.list_tools())
    assert {t.name for t in tools} == {"search", "list_conversations", "get_conversation",
                                       "list_artifacts", "get_artifact", "stats"}
