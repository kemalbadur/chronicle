"""Normalize a ChatGPT export into the canonical (Claude-style) schema.

A ChatGPT export stores each conversation as a `mapping` tree of nodes
(node id -> {id, message, parent, children}). This module rebuilds linear
message lists in the same shape build_index.py / synopsis.py consume for
Claude exports (see FORMAT.md), mirroring the standalone viewer's
JavaScript normalizer:

  - system and visually-hidden nodes are dropped; parents are rewired to
    the nearest kept ancestor so branching survives
  - content types map to blocks: text/multimodal_text -> text, code /
    execution_output -> fenced text, thoughts / reasoning_recap -> thinking
  - image/file attachments have no content in the export; they surface as
    files[] name references
  - conversation dates derive from message timestamps (ChatGPT sometimes
    stamps the top-level dates with the export date)

Deep Research prompts whose result is missing from the export are flagged
with "no_response": true.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

ROOT_PARENT = "00000000-0000-4000-8000-000000000000"


def looks_like_chatgpt(data: Any) -> bool:
    """True for a list of ChatGPT-style conversations (mapping trees)."""
    return isinstance(data, list) and any(
        isinstance(c, dict) and isinstance(c.get("mapping"), dict) for c in data
    )


def _iso(t: Any) -> str:
    """ChatGPT timestamps are unix seconds (floats); some are already strings."""
    if not t:
        return ""
    if isinstance(t, str):
        return t
    return (
        datetime.fromtimestamp(t, tz=UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _is_deep_research(message: dict[str, Any]) -> bool:
    offs = (
        (message.get("metadata") or {})
        .get("serialization_metadata", {})
        .get("custom_symbol_offsets")
    )
    return isinstance(offs, list) and any(
        isinstance(o, dict) and "deep_research" in str(o.get("id", "")).lower()
        for o in offs
    )


def _blocks(content: dict[str, Any] | None) -> tuple[list[dict[str, str]], int]:
    """One ChatGPT message's content -> (Claude-style blocks, image count)."""
    blocks: list[dict[str, str]] = []
    images = 0
    if not content:
        return blocks, images
    ct = content.get("content_type")
    parts = content.get("parts") or []
    str_parts = "\n\n".join(p for p in parts if isinstance(p, str))
    if ct == "text":
        if str_parts.strip():
            blocks.append({"type": "text", "text": str_parts})
    elif ct == "multimodal_text":
        txt: list[str] = []
        for p in parts:
            if isinstance(p, str):
                txt.append(p)
            elif isinstance(p, dict) and p.get("content_type") == "image_asset_pointer":
                images += 1
        joined = "\n\n".join(txt)
        if joined.strip():
            blocks.append({"type": "text", "text": joined})
    elif ct == "code":
        lang = content.get("language") or ""
        lang = "" if lang == "unknown" else lang
        if (content.get("text") or "").strip():
            blocks.append({"type": "text", "text": f"```{lang}\n{content['text']}\n```"})
    elif ct == "execution_output":
        if (content.get("text") or "").strip():
            blocks.append({"type": "text", "text": f"```\n{content['text']}\n```"})
    elif ct == "thoughts":
        t = "\n\n".join(
            (f"**{x.get('summary')}**\n" if x.get("summary") else "") + (x.get("content") or "")
            for x in (content.get("thoughts") or [])
        )
        if (t or str_parts).strip():
            blocks.append({"type": "thinking", "text": t or str_parts})
    elif ct == "reasoning_recap":
        if (content.get("content") or "").strip():
            blocks.append({"type": "thinking", "text": content["content"]})
    elif str_parts.strip():
        blocks.append({"type": "text", "text": str_parts})
    elif (content.get("text") or "").strip():
        blocks.append({"type": "text", "text": content["text"]})
    return blocks, images


def _nearest_kept(mapping: dict[str, Any], parent_id: str | None, kept: set[str]) -> str | None:
    """Walk up the parent chain to the nearest node that became a message."""
    pid = parent_id
    while pid:
        node = mapping.get(pid)
        if node is None:
            return None
        if pid in kept:
            return pid
        pid = node.get("parent")
    return None


def chatgpt_to_claude(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert a ChatGPT export (list of mapping-tree conversations)."""
    out: list[dict[str, Any]] = []
    for conv in data:
        mapping = conv.get("mapping") or {}
        # Pass 1: decide which nodes become messages (skip system/hidden/empty).
        kept: set[str] = set()
        built: dict[str, tuple[dict[str, Any], list[dict[str, str]], int]] = {}
        for nid, node in mapping.items():
            m = node.get("message")
            if not m or not m.get("author"):
                continue
            if m["author"].get("role") == "system":
                continue
            if (m.get("metadata") or {}).get("is_visually_hidden_from_conversation"):
                continue
            blocks, images = _blocks(m.get("content"))
            if not blocks and not images:
                continue
            kept.add(nid)
            built[nid] = (m, blocks, images)
        # Pass 2: emit messages, rewiring parents to the nearest kept ancestor.
        msgs: list[dict[str, Any]] = []
        for nid in kept:
            m, blocks, images = built[nid]
            parent = _nearest_kept(mapping, mapping[nid].get("parent"), kept)
            files = [{"file_name": "image (not included in export)"}] * images
            for att in (m.get("metadata") or {}).get("attachments") or []:
                files.append({"file_name": att.get("name") or "file"})
            msgs.append({
                "uuid": nid,
                "text": "",
                "content": blocks,
                "sender": "human" if m["author"].get("role") == "user" else "assistant",
                "created_at": _iso(m.get("create_time")),
                "attachments": [],
                "files": files,
                "parent_message_uuid": parent or ROOT_PARENT,
                "deep_research": _is_deep_research(m),
            })
        if not msgs:
            continue
        # Deep Research prompts with no reply: the export omits the result.
        answered = {x["parent_message_uuid"] for x in msgs}
        for x in msgs:
            x["no_response"] = bool(
                x.pop("deep_research") and x["sender"] == "human" and x["uuid"] not in answered
            )
        msgs.sort(key=lambda x: x["created_at"] or "")
        stamps = [x["created_at"] for x in msgs if x["created_at"]]
        out.append({
            "uuid": conv.get("conversation_id") or conv.get("id") or f"gpt-{len(out)}",
            "name": conv.get("title") or "(untitled)",
            "summary": "",
            "created_at": stamps[0] if stamps else _iso(conv.get("create_time")),
            "updated_at": stamps[-1] if stamps else _iso(conv.get("update_time")),
            "source": "chatgpt",
            "chat_messages": msgs,
        })
    return out
