"""/api/search ranking: exact hits, separate title matches (issues #12, #16)."""
from __future__ import annotations

import json
import threading

import pytest

pytest.importorskip("flask")

from conftest import search_corpus

import app as app_module
from build_index import build


@pytest.fixture()
def client(tmp_path, monkeypatch):
    src = tmp_path / "conversations.json"
    src.write_text(json.dumps(search_corpus()))
    db_path = tmp_path / "conversations.db"
    build(src, db_path)
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    monkeypatch.setattr(app_module, "_local", threading.local())
    return app_module.app.test_client()


def test_title_match_does_not_inflate_hits(client):
    convs = client.get("/api/search?q=antitrust").get_json()["conversations"]
    by_name = {c["name"]: c for c in convs}
    assert set(by_name) == {"Antitrust Deep Dive", "Weekly notes"}
    body_hit = by_name["Weekly notes"]
    title_hit = by_name["Antitrust Deep Dive"]
    assert body_hit["hits"] == 1 and body_hit["title_match"] is False
    # Title-only match: flagged, zero hits (not one per message), no snippet.
    assert title_hit["hits"] == 0 and title_hit["title_match"] is True
    assert title_hit["snippet"] is None
    # Body hits rank above title-only matches.
    assert convs[0]["name"] == "Weekly notes"


def test_search_covers_artifact_and_attachment_content(client):
    for q in ("zorblatt", "quuxfoo"):
        convs = client.get(f"/api/search?q={q}").get_json()["conversations"]
        assert [c["name"] for c in convs] == ["Dashboard build"]
        assert convs[0]["hits"] == 1 and "<<<" in convs[0]["snippet"]


def test_empty_query_and_missing_conversation(client):
    assert client.get("/api/search?q=").get_json()["conversations"] == []
    assert client.get("/api/conversation/nope").status_code == 404


def test_stats(client):
    s = client.get("/api/stats").get_json()
    assert s["conversations"] == 3 and s["messages"] == 6
