"""End-to-end tests for synopsis.py subcommands, on the generated sample zips."""
from __future__ import annotations

import argparse
import json

import pytest

import synopsis
from samples.build_samples import (
    CHATGPT_CONVERSATIONS,
    CLAUDE_CONVERSATIONS,
    CLAUDE_PROJECT,
    CLAUDE_PROJECT_UUID,
    write_zip,
)


@pytest.fixture(scope="session")
def claude_zip(tmp_path_factory):
    p = tmp_path_factory.mktemp("exports") / "claude.zip"
    write_zip(p, {
        "conversations.json": json.dumps(CLAUDE_CONVERSATIONS),
        f"projects/{CLAUDE_PROJECT_UUID}.json": json.dumps(CLAUDE_PROJECT),
    })
    return p


@pytest.fixture(scope="session")
def chatgpt_zip(tmp_path_factory):
    p = tmp_path_factory.mktemp("exports") / "chatgpt.zip"
    # Split files: load_export must merge conversations-000/001.
    write_zip(p, {
        "conversations-000.json": json.dumps(CHATGPT_CONVERSATIONS[:1]),
        "conversations-001.json": json.dumps(CHATGPT_CONVERSATIONS[1:]),
    })
    return p


def ns(**kw):
    return argparse.Namespace(**kw)


def test_load_export_claude(claude_zip):
    data = synopsis.load_export(claude_zip)
    assert len(data["conversations"]) == 3
    assert data["projects"][0]["name"] == "UChicago Facts"


def test_load_export_chatgpt_merges_and_normalizes(chatgpt_zip):
    data = synopsis.load_export(chatgpt_zip)
    convs = data["conversations"]
    assert len(convs) == 2
    assert all(c["source"] == "chatgpt" for c in convs)
    assert data["projects"] == []


def test_export_canonical_and_markdown(chatgpt_zip, tmp_path, capsys):
    synopsis.cmd_export(ns(export=str(chatgpt_zip), out=str(tmp_path / "canon"),
                           markdown=True))
    canon = json.loads((tmp_path / "canon" / "conversations.json").read_text())
    assert len(canon) == 2 and canon[0]["chat_messages"]
    md_dir = tmp_path / "canon" / "markdown"
    files = sorted(p.name for p in md_dir.glob("*.md"))
    assert "index.md" in files and len(files) == 3
    body = next(p for p in md_dir.glob("*.md") if p.name != "index.md").read_text()
    assert "## [0] You" in body and "ChatGPT" in body
