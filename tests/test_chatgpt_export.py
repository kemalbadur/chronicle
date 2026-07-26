"""chatgpt_export: mapping-tree normalization to the canonical schema."""
from __future__ import annotations

from chatgpt_export import ROOT_PARENT, _blocks, chatgpt_to_claude, looks_like_chatgpt
from samples.build_samples import CHATGPT_CONVERSATIONS, CLAUDE_CONVERSATIONS


def test_format_detection():
    assert looks_like_chatgpt(CHATGPT_CONVERSATIONS)
    assert not looks_like_chatgpt(CLAUDE_CONVERSATIONS)
    assert not looks_like_chatgpt({"mapping": {}})  # not a list


def test_sample_conversations_normalize():
    convs = chatgpt_to_claude(CHATGPT_CONVERSATIONS)
    assert [c["name"] for c in convs] == [
        "The UChicago Core Curriculum", "Days since Chicago Pile-1"]
    core = convs[0]
    assert core["source"] == "chatgpt"
    msgs = core["chat_messages"]
    # System node dropped; user root rewired to ROOT_PARENT; chain preserved.
    assert [m["sender"] for m in msgs] == ["human", "assistant"]
    assert msgs[0]["parent_message_uuid"] == ROOT_PARENT
    assert msgs[1]["parent_message_uuid"] == msgs[0]["uuid"]
    # Dates derive from message timestamps (unix seconds -> ISO).
    assert core["created_at"] == "2025-05-01T12:00:00Z"
    assert core["created_at"] == msgs[0]["created_at"]


def test_block_mapping_variants():
    code, _ = _blocks({"content_type": "code", "language": "python", "text": "x = 1"})
    assert code == [{"type": "text", "text": "```python\nx = 1\n```"}]
    unknown_lang, _ = _blocks({"content_type": "code", "language": "unknown", "text": "y"})
    assert unknown_lang[0]["text"].startswith("```\n")
    thoughts, _ = _blocks({"content_type": "thoughts",
                           "thoughts": [{"summary": "S", "content": "deep"}]})
    assert thoughts == [{"type": "thinking", "text": "**S**\ndeep"}]
    recap, _ = _blocks({"content_type": "reasoning_recap", "content": "recap"})
    assert recap[0]["type"] == "thinking"
    multi, images = _blocks({"content_type": "multimodal_text",
                             "parts": ["hello", {"content_type": "image_asset_pointer"}]})
    assert multi == [{"type": "text", "text": "hello"}] and images == 1
    assert _blocks(None) == ([], 0)


def test_hidden_and_empty_nodes_skipped_parent_rewired():
    conv = {
        "conversation_id": "c1", "title": "T",
        "mapping": {
            "root": {"id": "root", "message": None, "parent": None, "children": ["a"]},
            "a": {"id": "a", "parent": "root", "children": ["b"], "message": {
                "author": {"role": "user"}, "create_time": 100.0,
                "content": {"content_type": "text", "parts": ["question"]}, "metadata": {}}},
            "b": {"id": "b", "parent": "a", "children": ["c"], "message": {
                "author": {"role": "assistant"}, "create_time": 101.0,
                "content": {"content_type": "text", "parts": [""]},  # empty -> dropped
                "metadata": {}}},
            "c": {"id": "c", "parent": "b", "children": [], "message": {
                "author": {"role": "assistant"}, "create_time": 102.0,
                "content": {"content_type": "text", "parts": ["answer"]}, "metadata": {}}},
        },
    }
    msgs = chatgpt_to_claude([conv])[0]["chat_messages"]
    assert [m["uuid"] for m in msgs] == ["a", "c"]
    assert msgs[1]["parent_message_uuid"] == "a"  # rewired past dropped node b


def test_deep_research_prompt_without_reply_is_flagged():
    conv = {
        "conversation_id": "c2", "title": "DR",
        "mapping": {
            "a": {"id": "a", "parent": None, "children": [], "message": {
                "author": {"role": "user"}, "create_time": 100.0,
                "content": {"content_type": "text", "parts": ["research this"]},
                "metadata": {"serialization_metadata": {
                    "custom_symbol_offsets": [{"id": "deep_research_tag"}]}}}},
        },
    }
    msgs = chatgpt_to_claude([conv])[0]["chat_messages"]
    assert msgs[0]["no_response"] is True


def test_attachments_surface_as_file_references():
    conv = {
        "conversation_id": "c3", "title": "Files",
        "mapping": {
            "a": {"id": "a", "parent": None, "children": [], "message": {
                "author": {"role": "user"}, "create_time": 100.0,
                "content": {"content_type": "text", "parts": ["see attached"]},
                "metadata": {"attachments": [{"name": "report.pdf"}]}}},
        },
    }
    msgs = chatgpt_to_claude([conv])[0]["chat_messages"]
    assert msgs[0]["files"] == [{"file_name": "report.pdf"}]
