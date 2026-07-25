"""Transcript-rendering helpers: fences, heading demotion, slugs."""
from __future__ import annotations

from samples.build_samples import CLAUDE_CONVERSATIONS
from synopsis import _fence_for, chat_slug, demote_headings, render_transcript, slugify


def test_fence_for_scales_past_longest_backtick_run():
    assert _fence_for("no ticks") == "```"
    assert _fence_for("has ``` inside") == "````"
    assert _fence_for("`````") == "``````"


def test_demote_headings_basic_and_cap():
    assert demote_headings("## Two") == "### Two"
    assert demote_headings("##### Five") == "###### Five"
    assert demote_headings("###### Six stays") == "###### Six stays"
    assert demote_headings("#nospace stays") == "#nospace stays"


def test_demote_headings_skips_fenced_blocks():
    text = "```\n# not a heading\n```\n# heading"
    assert demote_headings(text) == "```\n# not a heading\n```\n## heading"


def test_demote_headings_mixed_fence_markers():
    # Regression: a ``` line inside a ~~~ block must not close the block.
    text = "~~~\n```\n# still fenced\n```\n~~~\n# heading"
    assert demote_headings(text) == "~~~\n```\n# still fenced\n```\n~~~\n## heading"


def test_slugify_and_chat_slug():
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("") == "untitled"
    assert len(slugify("x" * 200)) <= 60
    conv = {"name": "A crest for the Maroons", "created_at": "2026-05-09T16:40:00Z"}
    assert chat_slug(conv) == "2026-05-09-a-crest-for-the-maroons"


def test_render_transcript_smoke():
    out = render_transcript(CLAUDE_CONVERSATIONS[1])  # the artifact chat
    assert out.startswith("# Chicago Pile-1")
    assert "## [0] You" in out and "## [1] Claude" in out
    assert "_artifacts: UChicago milestones timeline_" in out
    out0 = render_transcript(CLAUDE_CONVERSATIONS[0])
    assert "_[thinking]_" in out0
