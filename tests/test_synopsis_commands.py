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


def test_propose_map_assigns_related_chats(claude_zip, tmp_path, capsys):
    out = tmp_path / "map.draft.json"
    synopsis.cmd_propose_map(ns(export=str(claude_zip), out=str(out), min_score=0.05))
    draft = json.loads(out.read_text())
    # The sample project "UChicago Facts" profiles Core/Fermi/Pile-1 topics;
    # at least the Pile-1 chat must land there, and the report must exist.
    assert "UChicago Facts" in draft
    assert "22222222-2222-4222-8222-222222222222" in draft["UChicago Facts"]
    report = out.with_suffix(".report.md").read_text()
    assert "propose-map report" in report and "margin" in report


def test_propose_map_requires_projects(chatgpt_zip, tmp_path):
    with pytest.raises(SystemExit):
        synopsis.cmd_propose_map(
            ns(export=str(chatgpt_zip), out=str(tmp_path / "m.json"), min_score=0.05))


def test_scrub_reports_then_applies(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    t = work / "chat.transcript.md"
    t.write_text(
        "My AWS key is AKIAIOSFODNN7EXAMPLE and my token ghp_"
        + "a" * 36 + "\nmail me at phoenix@uchicago.edu\n"
        "-----BEGIN RSA PRIVATE KEY-----\napi_key = 'abcd1234efgh5678'\n")
    synopsis.cmd_scrub(ns(work=str(work), apply=False))
    report = (work / "scrub-report.md").read_text()
    for kind in ("aws-access-key", "github-token", "email",
                 "private-key-block", "secret-assignment"):
        assert kind in report
    assert "AKIAIOSFODNN7EXAMPLE" in t.read_text()  # report-only: untouched

    synopsis.cmd_scrub(ns(work=str(work), apply=True))
    scrubbed = t.read_text()
    assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed
    assert "[REDACTED-aws-access-key]" in scrubbed
    assert "phoenix@uchicago.edu" not in scrubbed


def test_scrub_clean_tree(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "ok.md").write_text("nothing sensitive here\n")
    synopsis.cmd_scrub(ns(work=str(work), apply=False))
    assert "No matches" in (work / "scrub-report.md").read_text()


def make_work(tmp_path, briefs=("b1",), persona=False):
    """A minimal work/ dir: one project, chats c1/c2, briefs as requested."""
    work = tmp_path / "work"
    (work / "proj").mkdir(parents=True)
    manifest = {"projects": [{
        "name": "Proj", "slug": "proj", "uuid": "p-1", "description": "About proj.",
        "created_at": "2026-05-01T00:00:00Z", "updated_at": "", "project_memory": "",
        "chats": [
            {"uuid": "11111111-aaaa-4aaa-8aaa-111111111111", "title": "Chat One",
             "slug": "c1", "created_at": "2026-05-01T00:00:00Z", "updated_at": "",
             "transcript": "proj/c1.transcript.md", "brief": "proj/c1.brief.md"},
            {"uuid": "22222222-bbbb-4bbb-8bbb-222222222222", "title": "Chat Two",
             "slug": "c2", "created_at": "2026-05-02T00:00:00Z", "updated_at": "",
             "transcript": "proj/c2.transcript.md", "brief": "proj/c2.brief.md"},
        ]}]}
    (work / "manifest.json").write_text(json.dumps(manifest))
    if "b1" in briefs:
        (work / "proj" / "c1.brief.md").write_text("Brief one. " * 40)
    if "b2" in briefs:
        (work / "proj" / "c2.brief.md").write_text("Brief two. " * 40)
    if persona:
        (work / "_persona.md").write_text("# About me\n- concise\n")
    return work


def test_assemble_reports_sizes_and_missing(tmp_path, capsys):
    work = make_work(tmp_path)
    out = tmp_path / "out"
    synopsis.cmd_assemble(ns(work=str(work), out=str(out), max_chars=0))
    index = (out / "index.md").read_text()
    assert "KB" in index and "1 brief(s) missing" in index
    assert (out / "proj.md").exists() and (out / "proj.memory.md").exists()


def test_assemble_splits_on_budget_and_copies_persona(tmp_path, capsys):
    work = make_work(tmp_path, briefs=("b1", "b2"), persona=True)
    out = tmp_path / "out"
    synopsis.cmd_assemble(ns(work=str(work), out=str(out), max_chars=500))
    assert (out / "proj-1.md").exists() and (out / "proj-2.md").exists()
    assert not (out / "proj.md").exists()
    p1 = (out / "proj-1.md").read_text()
    assert "part 1/2" in p1 and "Chat One" in p1 and "Chat Two" not in p1
    assert (out / "persona.md").read_text().startswith("# About me")
    assert "persona.md" in (out / "index.md").read_text()


def test_resume_writes_primers_for_active_threads(claude_zip, tmp_path, capsys):
    out = tmp_path / "resume"
    # Sample chats span 2026-05-02..05-09; a 3-day window keeps only the crest chat.
    synopsis.cmd_resume(ns(export=str(claude_zip), days=3, tail=1, out=str(out)))
    files = list(out.glob("*.resume.md"))
    assert len(files) == 1 and "a-crest-for-the-maroons" in files[0].name
    body = files[0].read_text()
    assert body.startswith("# Resume: A crest for the Maroons")
    assert "the last 1 of 2 messages" in body and "How to use:" in body
