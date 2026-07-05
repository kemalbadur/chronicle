"""Generate two fake-but-realistic sample exports for Chronicle.

All content is invented conversation *around real, verifiable University of
Chicago facts* — so newcomers can try the viewer and the migration pipeline
without using their own data. Running this writes:

  samples/claude/   conversations.json, users.json, projects/<uuid>.json
  samples/chatgpt/  conversations.json
  samples/claude-uchicago-sample.zip     (drag into the viewer)
  samples/chatgpt-uchicago-sample.zip    (drag into the viewer)

The Claude sample has 3 chats, a project (with docs + custom instructions),
and two artifacts (an HTML timeline and an SVG crest). ChatGPT exports carry
no projects or artifacts, so its sample is 2 chats.

Run: python samples/build_samples.py
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT_PARENT = "00000000-0000-4000-8000-000000000000"
FIXED_ZIP_DATE = (2026, 1, 1, 0, 0, 0)  # deterministic zip bytes


# --------------------------------------------------------------------------- #
# Claude sample
# --------------------------------------------------------------------------- #
def text_block(t):
    return {"start_timestamp": "", "stop_timestamp": "", "type": "text", "text": t, "citations": []}


def thinking_block(t):
    return {"start_timestamp": "", "stop_timestamp": "", "type": "thinking", "text": t}


def artifact_block(aid, atype, title, content):
    return {"type": "tool_use", "name": "artifacts",
            "input": {"id": aid, "type": atype, "title": title, "command": "create", "content": content}}


def msg(uuid, sender, parent, when, blocks):
    return {"uuid": uuid, "text": "", "content": blocks, "sender": sender,
            "created_at": when, "updated_at": when, "attachments": [], "files": [],
            "parent_message_uuid": parent}


TIMELINE_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  body { font: 15px/1.5 Georgia, serif; color: #2b2a27; background: #faf9f7; margin: 20px; }
  h2 { color: #800000; }
  li { margin: 6px 0; }
  b { color: #800000; }
</style></head><body>
  <h2>University of Chicago — a few milestones</h2>
  <ul>
    <li><b>1890</b> — Founded, with a founding gift from John D. Rockefeller.</li>
    <li><b>1892</b> — Opens for classes under first president William Rainey Harper.</li>
    <li><b>1942</b> — Chicago Pile-1: first controlled nuclear chain reaction (Dec 2).</li>
    <li><b>Today</b> — Maroons, the Phoenix, and the Core in Hyde Park.</li>
  </ul>
  <p><em>Crescat scientia; vita excolatur.</em></p>
</body></html>"""

CREST_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 140" width="120" height="140">
  <path d="M60 4 L112 22 V78 C112 108 88 128 60 136 C32 128 8 108 8 78 V22 Z"
        fill="#800000" stroke="#5a0000" stroke-width="3"/>
  <text x="60" y="60" text-anchor="middle" font-family="Georgia, serif" font-size="30" fill="#f5f0e6">U</text>
  <text x="60" y="92" text-anchor="middle" font-family="Georgia, serif" font-size="30" fill="#f5f0e6">C</text>
  <text x="60" y="122" text-anchor="middle" font-family="Georgia, serif" font-size="11" fill="#e8cdba">MAROONS</text>
</svg>"""

CLAUDE_CONVERSATIONS = [
    {
        "uuid": "11111111-1111-4111-8111-111111111111",
        "name": "Who founded the University of Chicago?",
        "summary": "The user asks who founded UChicago; the assistant explains the 1890 Rockefeller founding and William Rainey Harper's first presidency.",
        "created_at": "2026-05-02T14:03:00Z",
        "updated_at": "2026-05-02T14:05:12Z",
        "account": {"uuid": "acct-phoenix"},
        "chat_messages": [
            msg("m-1a", "human", ROOT_PARENT, "2026-05-02T14:03:00Z",
                [text_block("Quick history question: who actually founded the University of Chicago, and when?")]),
            msg("m-1b", "assistant", "m-1a", "2026-05-02T14:05:12Z", [
                thinking_block("They want the founding of the *present* University of Chicago (1890), not the earlier 1856 institution. Name Rockefeller and Harper."),
                text_block("The present University of Chicago was founded in **1890**, with a founding gift from **John D. Rockefeller** (working with the American Baptist Education Society). It opened for classes in **1892** under its first president, **William Rainey Harper**, who built it as a research university with a college and graduate divisions from the start.\n\nIts motto is *Crescat scientia; vita excolatur* — \"Let knowledge grow from more to more; and so be human life enriched.\""),
            ]),
        ],
    },
    {
        "uuid": "22222222-2222-4222-8222-222222222222",
        "name": "Chicago Pile-1: the first nuclear reactor",
        "summary": "The user asks about the first nuclear reactor at UChicago; the assistant explains Chicago Pile-1 (Fermi, Dec 2 1942) and produces an HTML milestones timeline artifact.",
        "created_at": "2026-05-06T09:20:00Z",
        "updated_at": "2026-05-06T09:24:40Z",
        "account": {"uuid": "acct-phoenix"},
        "chat_messages": [
            msg("m-2a", "human", ROOT_PARENT, "2026-05-06T09:20:00Z",
                [text_block("Tell me about the first nuclear reactor at UChicago. And can you make me a little timeline I can drop in a page?")]),
            msg("m-2b", "assistant", "m-2a", "2026-05-06T09:24:40Z", [
                text_block("On **December 2, 1942**, a team led by **Enrico Fermi** achieved the first controlled, self-sustaining nuclear chain reaction in **Chicago Pile-1**, built in a squash court beneath the west viewing stands of the old **Stagg Field**. It was part of the Manhattan Project; the site is now marked by Henry Moore's sculpture *Nuclear Energy*.\n\nHere's a small timeline artifact you can embed:"),
                artifact_block("uchicago-timeline", "text/html", "UChicago milestones timeline", TIMELINE_HTML),
            ]),
        ],
    },
    {
        "uuid": "33333333-3333-4333-8333-333333333333",
        "name": "A crest for the Maroons",
        "summary": "The user asks for a simple maroon shield/crest; the assistant returns an SVG artifact.",
        "created_at": "2026-05-09T16:40:00Z",
        "updated_at": "2026-05-09T16:41:30Z",
        "account": {"uuid": "acct-phoenix"},
        "chat_messages": [
            msg("m-3a", "human", ROOT_PARENT, "2026-05-09T16:40:00Z",
                [text_block("Make me a simple maroon shield crest for the Maroons — just an SVG.")]),
            msg("m-3b", "assistant", "m-3a", "2026-05-09T16:41:30Z", [
                text_block("Here's a simple shield in UChicago maroon, with the Phoenix's colors:"),
                artifact_block("maroons-crest", "image/svg+xml", "Maroons crest", CREST_SVG),
            ]),
        ],
    },
]

CLAUDE_PROJECT_UUID = "44444444-4444-4444-8444-444444444444"
CLAUDE_PROJECT = {
    "uuid": CLAUDE_PROJECT_UUID,
    "name": "UChicago Facts",
    "description": "A place to keep verified facts and quick explainers about the University of Chicago.",
    "is_private": True,
    "is_starter_project": False,
    "prompt_template": "You are a University of Chicago history buff. Answer precisely, cite dates, and keep the Life of the Mind tone. When unsure, say so.",
    "created_at": "2026-05-01T12:00:00Z",
    "updated_at": "2026-05-09T16:41:30Z",
    "creator": {"uuid": "acct-phoenix", "full_name": "Phoenix Maroon"},
    "docs": [
        {"uuid": "doc-core", "filename": "core-curriculum.md",
         "content": "# The Common Core\n\nUChicago's general-education requirement, taught on the **quarter system**. Small discussion sections emphasize primary texts and the \"Life of the Mind.\" The Core spans the humanities, civilization studies, social sciences, and the physical/biological sciences.",
         "created_at": "2026-05-01T12:00:00Z"},
        {"uuid": "doc-fermi", "filename": "nobel-and-fermi.md",
         "content": "# Science on campus\n\n- **Chicago Pile-1** (Dec 2, 1942): first controlled nuclear chain reaction, led by Enrico Fermi under Stagg Field.\n- Roughly **100 Nobel laureates** have been affiliated with the university as faculty, students, or researchers.\n- The **Chicago school of economics** is associated with the university.",
         "created_at": "2026-05-01T12:00:00Z"},
    ],
}

CLAUDE_USERS = [{
    "uuid": "acct-phoenix",
    "full_name": "Phoenix Maroon",
    "email_address": "phoenix@uchicago.edu",
    "verified_phone_number": "+15555550190",
}]


# --------------------------------------------------------------------------- #
# ChatGPT sample (mapping-graph format; no projects/artifacts)
# --------------------------------------------------------------------------- #
def gpt_node(nid, role, parent, children, text, when):
    message = None
    if role is not None:
        message = {
            "id": nid, "author": {"role": role, "metadata": {}},
            "create_time": when,
            "content": {"content_type": "text", "parts": [text]},
            "metadata": {},
        }
    return {"id": nid, "message": message, "parent": parent, "children": children}


def gpt_conversation(cid, title, create_time, turns):
    """turns = [(role, text, when), ...] linearized into a mapping graph."""
    mapping = {"client-created-root": {"id": "client-created-root", "message": None,
                                       "parent": None, "children": ["sys"]}}
    mapping["sys"] = gpt_node("sys", "system", "client-created-root", [], "", create_time)
    prev = "sys"
    last_time = create_time
    for i, (role, text, when) in enumerate(turns):
        nid = f"{cid}-n{i}"
        mapping[prev]["children"] = [nid]
        mapping[nid] = gpt_node(nid, role, prev, [], text, when)
        prev = nid
        last_time = when
    return {"conversation_id": cid, "title": title,
            "create_time": create_time, "update_time": last_time, "mapping": mapping}


CHATGPT_CONVERSATIONS = [
    gpt_conversation(
        "gpt-core", "The UChicago Core Curriculum", 1746100800.0,
        [("user", "What is the University of Chicago's Core Curriculum, in a nutshell?", 1746100800.0),
         ("assistant", "The **Common Core** is UChicago's general-education program, taught on the **quarter system**. It's built around small discussion sections and primary texts across the humanities, civilization studies, social sciences, and the physical and biological sciences — the heart of the \"Life of the Mind\" ethos. Students take it alongside their major.", 1746100860.0)]),
    gpt_conversation(
        "gpt-pile", "Days since Chicago Pile-1", 1746205200.0,
        [("user", "Chicago Pile-1 went critical on Dec 2, 1942. Give me a tiny Python snippet to compute days since then.", 1746205200.0),
         ("assistant", "Chicago Pile-1 achieved the first self-sustaining nuclear chain reaction under Stagg Field on December 2, 1942. Here's a snippet:\n\n```python\nfrom datetime import date\ndays = (date.today() - date(1942, 12, 2)).days\nprint(f\"{days:,} days since Chicago Pile-1\")\n```\n\nSwap in any date to check an anniversary.", 1746205260.0)]),
]


# --------------------------------------------------------------------------- #
# Write files + zips
# --------------------------------------------------------------------------- #
def write_json(path: Path, obj) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    path.write_text(text)
    return text


def write_zip(zip_path: Path, members: dict[str, str]) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, data in members.items():
            info = zipfile.ZipInfo(arcname, date_time=FIXED_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)


def main() -> None:
    claude = HERE / "claude"
    chatgpt = HERE / "chatgpt"

    conv_txt = write_json(claude / "conversations.json", CLAUDE_CONVERSATIONS)
    users_txt = write_json(claude / "users.json", CLAUDE_USERS)
    proj_txt = write_json(claude / "projects" / f"{CLAUDE_PROJECT_UUID}.json", CLAUDE_PROJECT)
    gpt_txt = write_json(chatgpt / "conversations.json", CHATGPT_CONVERSATIONS)

    write_zip(HERE / "claude-uchicago-sample.zip", {
        "conversations.json": conv_txt,
        "users.json": users_txt,
        f"projects/{CLAUDE_PROJECT_UUID}.json": proj_txt,
    })
    write_zip(HERE / "chatgpt-uchicago-sample.zip", {
        "conversations.json": gpt_txt,
    })

    print(f"Claude sample:  {len(CLAUDE_CONVERSATIONS)} chats, 1 project, "
          f"2 artifacts -> claude-uchicago-sample.zip")
    print(f"ChatGPT sample: {len(CHATGPT_CONVERSATIONS)} chats -> chatgpt-uchicago-sample.zip")


if __name__ == "__main__":
    main()
