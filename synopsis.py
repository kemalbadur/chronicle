"""Migrate a Claude/ChatGPT history into per-project knowledge + memory.

The export has no chat<->project mapping, so the user supplies the chat list per
project. This tool does the deterministic work (parse, match, extract, assemble);
the per-chat brief and per-project memory synthesis are written by Claude Code in
between (prompt styles live in prompts/). No API key, all stdlib.
Full walkthrough: MIGRATE.md.

Workflow:
  1. python synopsis.py list --export EXPORT.zip [--since YYYY-MM-DD]
        -> a table of every chat (uuid / date / msgs / title) to help build the map
  2. python synopsis.py build-map --export EXPORT.zip --listings project_listings --out map.json
        -> resolves project_listings/*.md to a map.json (uuid / title / title+date)
  3. python synopsis.py prepare --export EXPORT.zip --map map.json --out work/
        -> per-chat transcript bundles + work/manifest.json + a match report
  4. (Claude Code) read each *.transcript.md, write *.brief.md alongside it
        (see prompts/style-a.md, style-b.md, style-c.md)
  5. python synopsis.py assemble --work work/ --out out/
        -> per-project document (<project>.md) + memory block (<project>.memory.md)
           + index.md

map.json format (uuid preferred, exact title accepted):
  {
    "Office of AI": ["0199d8f2-0ad6-72ff-9cc2-e7d20170b202", "Exact Chat Title"],
    "Another Project": ["..."]
  }
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

# Reuse the export's block-extraction helpers rather than re-implement them.
from build_index import _join_blocks, _tool_names

CARD_TOOLS = {"artifacts", "create_file"}
UUID_RE = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)


# --------------------------------------------------------------------------- #
# Export reading
# --------------------------------------------------------------------------- #
def load_export(zip_path: Path) -> dict[str, Any]:
    """Read the parts of the export we need into memory."""
    if not zip_path.exists():
        sys.exit(f"Export not found: {zip_path}")
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        if "conversations.json" not in names:
            sys.exit("conversations.json not found in export (is this a Claude export?)")
        with zf.open("conversations.json") as fh:
            conversations = json.load(fh)
        projects = []
        for name in names:
            if name.startswith("projects/") and name.endswith(".json"):
                with zf.open(name) as fh:
                    projects.append(json.load(fh))
        project_memories: dict[str, str] = {}
        if "memories.json" in names:
            with zf.open("memories.json") as fh:
                mem = json.load(fh)
            if isinstance(mem, list) and mem:
                project_memories = mem[0].get("project_memories") or {}
    return {
        "conversations": conversations,
        "projects": projects,
        "project_memories": project_memories,
    }


# --------------------------------------------------------------------------- #
# Transcript rendering
# --------------------------------------------------------------------------- #
def _fence_for(text: str) -> str:
    """Pick a backtick fence longer than any run of backticks in text."""
    longest = max((len(m) for m in re.findall(r"`+", text or "")), default=0)
    return "`" * max(3, longest + 1)


def _render_tool_cards(content: list[dict[str, Any]]) -> list[str]:
    """Render artifact / create_file tool_use blocks as fenced content."""
    out: list[str] = []
    for block in content:
        if block.get("type") != "tool_use" or block.get("name") not in CARD_TOOLS:
            continue
        inp = block.get("input") or {}
        title = inp.get("title") or inp.get("path") or block["name"]
        text = inp.get("content") or inp.get("file_text") or ""
        if not text:
            continue
        fence = _fence_for(text)
        out.append(f"_{block['name']}: {title}_\n{fence}\n{text}\n{fence}")
    return out


def _render_attachments(message: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for att in message.get("attachments") or []:
        text = att.get("extracted_content")
        if not text:
            continue
        name = att.get("file_name") or "attachment"
        fence = _fence_for(text)
        out.append(f"_attached: {name}_\n{fence}\n{text}\n{fence}")
    return out


def render_transcript(conv: dict[str, Any]) -> str:
    """Full, faithful Markdown transcript of a conversation."""
    lines: list[str] = []
    name = conv.get("name") or "(untitled)"
    lines.append(f"# {name}")
    lines.append(
        f"_{conv.get('created_at', '')[:16]} -> {conv.get('updated_at', '')[:16]} "
        f"| {len(conv.get('chat_messages', []))} messages | uuid {conv.get('uuid')}_"
    )
    if (conv.get("summary") or "").strip():
        lines.append("\n> **Export's own (memory-style) summary, for context only:**")
        for para in conv["summary"].split("\n"):
            lines.append(f"> {para}")

    for seq, msg in enumerate(conv.get("chat_messages", [])):
        content = msg.get("content") or []
        speaker = "You" if msg.get("sender") == "human" else "Claude"
        lines.append(f"\n## [{seq}] {speaker}")
        for att in _render_attachments(msg):
            lines.append(att)
        body = _join_blocks(content, "text") or (msg.get("text") or "")
        if body.strip():
            lines.append(body)
        thinking = _join_blocks(content, "thinking")
        if thinking.strip():
            lines.append(f"_[thinking]_\n{thinking}")
        for card in _render_tool_cards(content):
            lines.append(card)
        other = [
            n for n in (_tool_names(content) or "").split(", ")
            if n and n not in CARD_TOOLS
        ]
        if other:
            lines.append(f"_[tools used: {', '.join(other)}]_")
    return "\n\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def demote_headings(markdown: str) -> str:
    """Shift ATX headings down one level (## -> ###) so a brief nests under
    its chat title. Skips lines inside fenced code blocks."""
    out: list[str] = []
    in_fence = False
    for line in markdown.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
        elif not in_fence:
            m = re.match(r"^(#{1,5}) (?=\S)", line)
            if m:
                line = "#" + line
        out.append(line)
    return "\n".join(out)


def slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (slug[:max_len].rstrip("-")) or "untitled"


def chat_slug(conv: dict[str, Any]) -> str:
    date = (conv.get("created_at") or "")[:10]
    return f"{date}-{slugify(conv.get('name') or 'untitled')}"


def build_indexes(conversations: list[dict[str, Any]]):
    by_uuid = {c["uuid"]: c for c in conversations}
    by_title: dict[str, list[dict[str, Any]]] = {}
    for c in conversations:
        by_title.setdefault((c.get("name") or "").strip(), []).append(c)
    return by_uuid, by_title


def title_date_index(conversations: list[dict[str, Any]]):
    """(title, updated_date[:10]) -> [conv] for disambiguating duplicate titles."""
    idx: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for c in conversations:
        key = ((c.get("name") or "").strip(), (c.get("updated_at") or "")[:10])
        idx.setdefault(key, []).append(c)
    return idx


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^([A-Za-z]{3,9}) (\d{1,2}), (\d{4})$")


def _to_iso(text: str) -> str | None:
    text = text.strip()
    if _ISO_RE.match(text):
        return text
    m = _MONTH_RE.match(text)
    if m and m.group(1)[:3].lower() in _MONTHS:
        return f"{m.group(3)}-{_MONTHS[m.group(1)[:3].lower()]:02d}-{int(m.group(2)):02d}"
    return None


def parse_listing(path: Path) -> list[dict[str, str | None]]:
    """Extract {title, uuid, date} rows from a project listing .md file.

    Handles Markdown tables (any column order) and `N. Title — date` lists.
    """
    rows: list[dict[str, str | None]] = []
    for line in path.read_text().splitlines():
        s = line.strip()
        uu = UUID_RE.search(s) or re.search(
            r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", s, re.I)
        uuid = uu.group(1).lower() if uu else None
        title: str | None = None
        date: str | None = None
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(set(c) <= {"-", ":"} for c in cells):  # separator row
                continue
            candidates: list[str] = []
            for c in cells:
                iso = _to_iso(c)
                if iso:
                    date = date or iso
                    continue
                cl = c.lower()
                if cl in {"", "title", "chat", "date", "link", "url", "#",
                          "last updated", "date (updated)"}:
                    continue
                if c.isdigit() or c.startswith("http") or "claude.ai/chat" in c:
                    continue
                candidates.append(c)
            if candidates:
                title = max(candidates, key=len)
        else:
            m = re.match(r"^\d+\.\s+(.*?)\s+[—-]\s+(\d{4}-\d{2}-\d{2})\s*$", s)
            if m:
                title, date = m.group(1).strip(), m.group(2)
        if title or uuid:
            rows.append({"title": title, "uuid": uuid, "date": date})
    return rows


def resolve_row(row, by_uuid, by_title, by_title_date):
    """Resolve a parsed listing row to (conv, note); conv is None if unresolved."""
    uuid, title, date = row["uuid"], row["title"], row["date"]
    if uuid:
        if uuid in by_uuid:
            return by_uuid[uuid], "uuid"
        return None, f"UUID not in export ({uuid})"
    titled = by_title.get((title or "").strip(), [])
    if len(titled) == 1:
        return titled[0], "title"
    if len(titled) > 1:
        if date:
            dated = by_title_date.get(((title or "").strip(), date), [])
            if len(dated) == 1:
                return dated[0], "title+date"
            if len(dated) > 1:
                return None, f"AMBIGUOUS even with date {date} ({len(dated)} chats)"
        return None, f"AMBIGUOUS title ({len(titled)} chats; date did not disambiguate)"
    return None, "UNMATCHED (no uuid or exact title match)"


def resolve(identifier: str, by_uuid, by_title):
    """Return (conv, note). conv is None when unmatched/ambiguous."""
    ident = identifier.strip()
    if ident in by_uuid:
        return by_uuid[ident], "uuid"
    # uuid prefix (only if unambiguous)
    if re.fullmatch(r"[0-9a-f-]{6,}", ident, re.I) and not UUID_RE.match(ident):
        hits = [c for u, c in by_uuid.items() if u.startswith(ident.lower())]
        if len(hits) == 1:
            return hits[0], "uuid-prefix"
        if len(hits) > 1:
            return None, f"AMBIGUOUS uuid prefix ({len(hits)} chats match)"
    # exact title
    titled = by_title.get(ident, [])
    if len(titled) == 1:
        return titled[0], "title"
    if len(titled) > 1:
        return None, f"AMBIGUOUS title ({len(titled)} chats share it — use a uuid)"
    return None, "UNMATCHED (no uuid or exact title match)"


def project_meta_for(name: str, projects: list[dict[str, Any]]):
    for p in projects:
        if (p.get("name") or "").strip() == name.strip():
            return p
    return None


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_list(args) -> None:
    data = load_export(Path(args.export))
    convs = data["conversations"]
    if args.since:
        convs = [
            c for c in convs
            if (c.get("updated_at") or c.get("created_at") or "")[:10] >= args.since
        ]
    convs = sorted(convs, key=lambda c: c.get("updated_at") or "", reverse=True)
    lines = [
        f"Chats: {len(convs)}"
        + (f" (updated since {args.since})" if args.since else ""),
        "",
        "| uuid | updated | msgs | title |",
        "|------|---------|------|-------|",
    ]
    for c in convs:
        title = (c.get("name") or "(untitled)").replace("|", "\\|")
        lines.append(
            f"| {c['uuid']} | {(c.get('updated_at') or '')[:16]} "
            f"| {len(c.get('chat_messages', []))} | {title} |"
        )
    out = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(out)
        print(f"Wrote {args.out} ({len(convs)} chats)")
    else:
        print(out)


def cmd_build_map(args) -> None:
    data = load_export(Path(args.export))
    by_uuid, by_title = build_indexes(data["conversations"])
    by_td = title_date_index(data["conversations"])
    proj_names = {(p.get("name") or "").strip().lower(): (p.get("name") or "").strip()
                  for p in data["projects"] if (p.get("name") or "").strip()}

    the_map: dict[str, list[str]] = {}
    report: list[str] = ["# build-map report", ""]
    total_ok = total_bad = 0
    for path in sorted(Path(args.listings).glob("*.md")):
        rows = parse_listing(path)
        # align the project name to the export's exact name when possible
        proj = proj_names.get(path.stem.lower(), path.stem)
        note = "" if path.stem.lower() in proj_names else "  ⚠ no matching export project"
        report.append(f"## {proj}  (from {path.name}){note}")
        uuids: list[str] = []
        seen: set[str] = set()
        for row in rows:
            conv, why = resolve_row(row, by_uuid, by_title, by_td)
            label = row["title"] or row["uuid"] or "?"
            if conv is None:
                total_bad += 1
                report.append(f"- [ ] {label} — **{why}**")
                continue
            if conv["uuid"] in seen:
                report.append(f"- [=] {label} — duplicate, already added")
                continue
            seen.add(conv["uuid"])
            uuids.append(conv["uuid"])
            total_ok += 1
        the_map[proj] = uuids
        report.append(f"_resolved {len(uuids)} chats_\n")

    Path(args.out).write_text(json.dumps(the_map, indent=2))
    report_path = Path(args.out).with_suffix(".report.md")
    report_path.write_text("\n".join(report) + "\n")
    print(f"Wrote {args.out}: {sum(len(v) for v in the_map.values())} chats "
          f"across {len(the_map)} projects ({total_bad} unresolved).")
    print(f"Report: {report_path}")
    if total_bad:
        print(f"  ⚠ {total_bad} row(s) unresolved — see report to fix by hand.")


def cmd_prepare(args) -> None:
    data = load_export(Path(args.export))
    by_uuid, by_title = build_indexes(data["conversations"])
    the_map = json.loads(Path(args.map).read_text())
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {"projects": []}
    report: list[str] = ["# Match report", ""]
    total_ok = total_bad = 0

    for proj_name, identifiers in the_map.items():
        pslug = slugify(proj_name)
        pdir = out_dir / pslug
        pdir.mkdir(parents=True, exist_ok=True)
        pmeta = project_meta_for(proj_name, data["projects"])
        puuid = pmeta.get("uuid") if pmeta else None
        entry: dict[str, Any] = {
            "name": proj_name,
            "slug": pslug,
            "uuid": puuid,
            "description": (pmeta or {}).get("description", ""),
            "created_at": (pmeta or {}).get("created_at", ""),
            "updated_at": (pmeta or {}).get("updated_at", ""),
            "project_memory": data["project_memories"].get(puuid, "") if puuid else "",
            "chats": [],
        }
        report.append(f"## {proj_name}"
                      + ("" if pmeta else "  _(no matching project file in export)_"))
        used_slugs: set[str] = set()
        for ident in identifiers:
            conv, note = resolve(ident, by_uuid, by_title)
            if conv is None:
                total_bad += 1
                report.append(f"- [ ] `{ident}` — **{note}**")
                continue
            total_ok += 1
            cslug = chat_slug(conv)
            if cslug in used_slugs:  # same created-date + title: disambiguate
                cslug = f"{cslug}-{conv['uuid'][:8]}"
            used_slugs.add(cslug)
            tpath = pdir / f"{cslug}.transcript.md"
            tpath.write_text(render_transcript(conv))
            report.append(
                f"- [x] `{ident}` -> {conv['uuid']} ({note}) — "
                f"\"{conv.get('name') or '(untitled)'}\""
            )
            entry["chats"].append({
                "uuid": conv["uuid"],
                "title": conv.get("name") or "(untitled)",
                "slug": cslug,
                "created_at": conv.get("created_at", ""),
                "updated_at": conv.get("updated_at", ""),
                "transcript": str(tpath.relative_to(out_dir)),
                "brief": f"{pslug}/{cslug}.brief.md",
            })
        manifest["projects"].append(entry)

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (out_dir / "match-report.md").write_text("\n".join(report) + "\n")
    print(f"Prepared {total_ok} chats across {len(the_map)} projects "
          f"({total_bad} unmatched) -> {out_dir}")
    print(f"  manifest:     {out_dir / 'manifest.json'}")
    print(f"  match report: {out_dir / 'match-report.md'}")
    if total_bad:
        print(f"  ⚠ {total_bad} identifier(s) unmatched/ambiguous — see match report.")
    print("\nNext: generate a *.brief.md next to each *.transcript.md "
          "(Claude Code agents), then run `assemble`.")


def cmd_assemble(args) -> None:
    work = Path(args.work)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((work / "manifest.json").read_text())

    index = ["# Project knowledge index", ""]
    for proj in manifest["projects"]:
        pslug = proj["slug"]
        doc = [f"# {proj['name']} — chat knowledge", ""]
        if proj.get("description"):
            doc.append(proj["description"] + "\n")
        doc.append(
            f"_{len(proj['chats'])} chats"
            + (f" | project created {proj['created_at'][:10]}" if proj.get("created_at") else "")
            + "_\n"
        )
        doc.append("## Contents\n")
        for c in proj["chats"]:
            doc.append(f"- [{c['title']}](#{slugify(c['title'])}) — {c['created_at'][:10]}")
        doc.append("")

        missing = []
        for c in proj["chats"]:
            brief_path = work / c["brief"]
            doc.append(f'\n<a id="{slugify(c["title"])}"></a>\n')
            doc.append(f"## {c['title']}")
            doc.append(f"_{c['created_at'][:10]} · chat uuid {c['uuid']}_\n")
            if brief_path.exists():
                doc.append(demote_headings(brief_path.read_text().strip()))
            else:
                missing.append(c["brief"])
                doc.append("_(brief not yet generated)_")
        doc_path = out_dir / f"{pslug}.md"
        doc_path.write_text("\n".join(doc) + "\n")

        # Memory block: fresh cross-chat synthesis (if generated) first, then
        # the export's curated memory, then the folded-chat index.
        mem = [f"# {proj['name']} — memory block", ""]
        syn = work / pslug / "_synthesis.md"
        if syn.exists():
            mem.append(syn.read_text().strip() + "\n")
        if proj.get("project_memory"):
            mem.append("## Prior curated memory (from export)\n")
            mem.append(proj["project_memory"].strip() + "\n")
        mem.append("## Chats folded into project knowledge\n")
        for c in proj["chats"]:
            mem.append(f"- {c['title']} ({c['created_at'][:10]})")
        (out_dir / f"{pslug}.memory.md").write_text("\n".join(mem) + "\n")

        index.append(f"- [{proj['name']}]({pslug}.md) — {len(proj['chats'])} chats"
                     + (f"  ⚠ {len(missing)} brief(s) missing" if missing else ""))
        print(f"Assembled {proj['name']}: {doc_path}"
              + (f"  (⚠ {len(missing)} briefs missing)" if missing else ""))

    (out_dir / "index.md").write_text("\n".join(index) + "\n")
    print(f"Index: {out_dir / 'index.md'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="dump all chats to help build map.json")
    p_list.add_argument("--export", required=True)
    p_list.add_argument("--since", help="only chats updated on/after YYYY-MM-DD")
    p_list.add_argument("--out", help="write to file instead of stdout")
    p_list.set_defaults(func=cmd_list)

    p_map = sub.add_parser("build-map", help="build map.json from project_listings/*.md")
    p_map.add_argument("--export", required=True)
    p_map.add_argument("--listings", default="project_listings")
    p_map.add_argument("--out", default="map.json")
    p_map.set_defaults(func=cmd_build_map)

    p_prep = sub.add_parser("prepare", help="extract transcript bundles per project")
    p_prep.add_argument("--export", required=True)
    p_prep.add_argument("--map", required=True)
    p_prep.add_argument("--out", default="work")
    p_prep.set_defaults(func=cmd_prepare)

    p_asm = sub.add_parser("assemble", help="combine briefs into docs + memory blocks")
    p_asm.add_argument("--work", default="work")
    p_asm.add_argument("--out", default="out")
    p_asm.set_defaults(func=cmd_assemble)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
