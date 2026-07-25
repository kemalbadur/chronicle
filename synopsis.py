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
from chatgpt_export import chatgpt_to_claude, looks_like_chatgpt

CARD_TOOLS = {"artifacts", "create_file"}
UUID_RE = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)


# --------------------------------------------------------------------------- #
# Export reading
# --------------------------------------------------------------------------- #
def load_export(zip_path: Path) -> dict[str, Any]:
    """Read the parts of the export we need into memory.

    Accepts a Claude export (conversations.json [+ projects/, memories.json])
    or a ChatGPT export (conversations.json, possibly split into
    conversations-000.json, ...), which is normalized to the Claude shape.
    """
    if not zip_path.exists():
        sys.exit(f"Export not found: {zip_path}")
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        conv_names = sorted(
            n for n in names
            if re.fullmatch(r"(?:[^/]+/)?conversations(-\d+)?\.json", n)
        )
        if not conv_names:
            sys.exit("No conversations file found in export "
                     "(looked for conversations.json / conversations-000.json).")
        conversations: list[dict[str, Any]] = []
        for n in conv_names:
            with zf.open(n) as fh:
                part = json.load(fh)
            if isinstance(part, list):
                conversations.extend(part)
        if looks_like_chatgpt(conversations):
            conversations = chatgpt_to_claude(conversations)
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
    longest = max((len(m.group()) for m in re.finditer(r"`+", text or "")), default=0)
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

    assistant = "ChatGPT" if conv.get("source") == "chatgpt" else "Claude"
    for seq, msg in enumerate(conv.get("chat_messages", [])):
        content = msg.get("content") or []
        speaker = "You" if msg.get("sender") == "human" else assistant
        lines.append(f"\n## [{seq}] {speaker}")
        if msg.get("no_response"):
            lines.append("_[Deep Research request — the result is not included "
                         "in ChatGPT's export; only this prompt was saved.]_")
        for att in _render_attachments(msg):
            lines.append(att)
        for f in msg.get("files") or []:
            if f.get("file_name"):
                lines.append(f"_[uploaded: {f['file_name']} — content not in export]_")
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
    fence: str | None = None  # the marker that opened the current code block
    for line in markdown.splitlines():
        m_fence = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m_fence:
            marker = m_fence.group(1)
            if fence is None:
                fence = marker
            # Per CommonMark, only a same-char fence at least as long closes it,
            # so a ``` line inside a ~~~ block stays literal (and vice versa).
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
        elif fence is None:
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

    Caveat: in a table row, the *longest* cell that isn't a date, number, URL,
    or known header is assumed to be the title — a long free-text column (e.g.
    "notes") can steal it. The build-map match report surfaces the resulting
    unmatched/ambiguous rows, so check it after running.
    """
    rows: list[dict[str, str | None]] = []
    for line in path.read_text().splitlines():
        s = line.strip()
        # (Not UUID_RE: its anchored repeated group would make group(1) just
        # the last "-xxxx" chunk on a bare-uuid line.)
        uu = re.search(
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
# Rehydrate: recover generated documents by re-running docgen scripts
# --------------------------------------------------------------------------- #
# Same detector the viewer uses for its "this is code, not the document" note.
DOCGEN = re.compile(
    r"(require\(['\"]docx|from docx import|pptxgenjs|require\(['\"]exceljs"
    r"|require\(['\"]xlsx|openpyxl|reportlab|require\(['\"]pdfkit|from pptx import)",
    re.I,
)


def _doc_kind(text: str) -> str:
    if re.search(r"docx", text, re.I):
        return "Word (.docx)"
    if re.search(r"pptx", text, re.I):
        return "PowerPoint (.pptx)"
    if re.search(r"exceljs|xlsx|openpyxl", text, re.I):
        return "Excel (.xlsx)"
    if re.search(r"reportlab|pdfkit", text, re.I):
        return "PDF"
    return "document"


def _script_lang(text: str) -> str:
    if re.search(r"require\(['\"]|module\.exports|pptxgenjs", text):
        return "js"
    if re.search(r"^\s*(from|import)\s+\w+", text, re.M):
        return "py"
    return "txt"


def find_docgen_scripts(conversations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Document-generator scripts across all chats, deduped by (chat, title)
    keeping the last (most recent) full version."""
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for conv in conversations:
        for msg in conv.get("chat_messages", []):
            for block in msg.get("content") or []:
                if block.get("type") != "tool_use":
                    continue
                inp = block.get("input") or {}
                if block.get("name") == "artifacts":
                    text = inp.get("content") or ""   # full versions only
                    title = inp.get("title") or inp.get("id") or "artifact"
                elif block.get("name") == "create_file":
                    text = inp.get("file_text") or ""
                    title = (inp.get("path") or "file").rsplit("/", 1)[-1]
                else:
                    continue
                if not text or not DOCGEN.search(text):
                    continue
                found[(conv["uuid"], title)] = {
                    "conv_uuid": conv["uuid"],
                    "conv_name": conv.get("name") or "(untitled)",
                    "conv_slug": chat_slug(conv),
                    "title": title,
                    "text": text,
                    "kind": _doc_kind(text),
                    "lang": _script_lang(text),
                }
    return list(found.values())


def cmd_rehydrate(args) -> None:
    import subprocess

    data = load_export(Path(args.export))
    scripts = find_docgen_scripts(data["conversations"])
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not scripts:
        print("No document-generator scripts found in this export.")
        return
    if args.run:
        print("⚠ --run executes code that was stored in your export. Only do "
              "this with your own history, and expect failures where scripts "
              "need packages (docx, pptxgenjs, ...) you haven't installed.")
    report = ["# Rehydrate report", "",
              f"_{len(scripts)} document-generator script(s) found._", ""]
    ran = ok = 0
    for s in scripts:
        sdir = out_dir / s["conv_slug"]
        sdir.mkdir(parents=True, exist_ok=True)
        base = slugify(s["title"]) or "script"
        ext = {"js": ".js", "py": ".py"}.get(s["lang"], ".txt")
        spath = sdir / f"{base}{ext}"
        n = 2
        while spath.exists() and spath.read_text() != s["text"]:
            spath = sdir / f"{base}-{n}{ext}"
            n += 1
        spath.write_text(s["text"])
        report.append(f"## {s['title']}  ({s['kind']})")
        report.append(f"- from chat: {s['conv_name']}")
        report.append(f"- script: `{spath.relative_to(out_dir)}`")
        if args.run and ext != ".txt":
            ran += 1
            runner = ["node", spath.name] if ext == ".js" else [sys.executable, spath.name]
            before = {p.name for p in sdir.iterdir()}
            try:
                proc = subprocess.run(
                    runner, cwd=sdir, capture_output=True, text=True,
                    timeout=args.timeout,
                )
                log = proc.stdout + proc.stderr
                status = "ok" if proc.returncode == 0 else f"exit {proc.returncode}"
            except FileNotFoundError:
                log, status = f"{runner[0]} not installed", "no runtime"
            except subprocess.TimeoutExpired:
                log, status = f"timed out after {args.timeout}s", "timeout"
            spath.with_suffix(spath.suffix + ".log").write_text(log)
            created = sorted(
                p for p in ({q.name for q in sdir.iterdir()} - before)
                if not p.endswith(".log")
            )
            if status == "ok":
                ok += 1
                report.append(f"- **ran ok** — created: "
                              f"{', '.join(created) if created else '(no new files)'}")
            else:
                report.append(f"- **failed** ({status}) — see "
                              f"`{spath.relative_to(out_dir)}.log`")
        elif args.run:
            report.append("- skipped (could not tell if Node or Python)")
        report.append("")
    (out_dir / "rehydrate-report.md").write_text("\n".join(report) + "\n")
    summary = (f"{ok}/{ran} script(s) ran clean; " if args.run else "")
    print(f"{len(scripts)} script(s) extracted -> {out_dir}. "
          f"{summary}Report: {out_dir / 'rehydrate-report.md'}")
    if not args.run:
        print("Nothing was executed. Re-run with --run to regenerate the "
              "documents (needs node / the scripts' packages installed).")


# --------------------------------------------------------------------------- #
# Scrub: secret/PII detection over prepared transcripts
# --------------------------------------------------------------------------- #
# Order matters: more specific patterns first (sk-ant- before sk-).
SCRUB_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("jwt", re.compile(
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{5,}\b")),
    ("secret-assignment", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|passwd|password)\b\s*[:=]\s*"
        r"['\"]?[A-Za-z0-9_\-/+.]{12,}")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("phone", re.compile(r"\+\d[\d ().-]{7,}\d")),
]


def scrub_text(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Return (redacted_text, findings). Findings carry line/type/preview."""
    findings: list[dict[str, Any]] = []
    for kind, pat in SCRUB_PATTERNS:
        for m in pat.finditer(text):
            token = m.group()
            findings.append({
                "type": kind,
                "line": text.count("\n", 0, m.start()) + 1,
                "preview": token[:6] + "…" if len(token) > 9 else token[:3] + "…",
            })
        text = pat.sub(f"[REDACTED-{kind}]", text)
    return text, findings


def cmd_scrub(args) -> None:
    work = Path(args.work)
    paths = sorted(p for p in work.rglob("*.md") if not p.name.startswith("scrub-"))
    if not paths:
        sys.exit(f"No .md files under {work} — run `prepare` first.")
    report = ["# Scrub report", "",
              "Matches found by pattern scan. **Review before uploading anything.**",
              "Re-run with `--apply` to redact these in place.", ""]
    total = 0
    for path in paths:
        original = path.read_text()
        redacted, findings = scrub_text(original)
        if not findings:
            continue
        total += len(findings)
        report.append(f"## {path.relative_to(work)}")
        for f in findings:
            report.append(f"- line {f['line']}: **{f['type']}** `{f['preview']}`")
        report.append("")
        if args.apply:
            path.write_text(redacted)
    if total == 0:
        report.append("_No matches found._")
    report_path = work / "scrub-report.md"
    report_path.write_text("\n".join(report) + "\n")
    action = "redacted in place" if args.apply else "found (nothing changed)"
    print(f"{total} match(es) {action}. Report: {report_path}")
    if total and not args.apply:
        print("Review the report, then: python synopsis.py scrub --work "
              f"{work} --apply")
    print("For judgment calls regexes can't make (names, health, salary), "
          "run a model pass with prompts/scrub.md.")


# --------------------------------------------------------------------------- #
# Map proposal (lexical scoring, no model, no network)
# --------------------------------------------------------------------------- #
_STOP = frozenset(
    "a an and are as at be but by for from has have i if in is it its me my of on or "
    "so that the this to was we what when which with you your can could should would "
    "do does did how not no yes just like get make want need help please also".split()
)


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]{3,}", (text or "").lower()) if t not in _STOP]


def _chat_text(conv: dict[str, Any], max_chars: int = 4000) -> str:
    """Title (weighted by repetition) + the first stretch of message text."""
    parts = [(conv.get("name") or "") * 3]
    total = 0
    for m in conv.get("chat_messages", []):
        body = _join_blocks(m.get("content") or [], "text") or (m.get("text") or "")
        parts.append(body[: max_chars - total])
        total += len(body)
        if total >= max_chars:
            break
    return "\n".join(parts)


def propose_map(
    conversations: list[dict[str, Any]],
    projects: list[dict[str, Any]],
    min_score: float = 0.05,
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    """Score every chat against every project profile; return (draft_map, rows).

    Cosine similarity over IDF-weighted term counts. Each row carries the
    top-2 candidates and a confidence margin so a human can review the
    low-margin assignments. Purely lexical — a reviewable first draft, not
    a decision.
    """
    import math
    from collections import Counter

    chat_tokens = {c["uuid"]: Counter(_tokens(_chat_text(c))) for c in conversations}
    # IDF over the chat corpus (projects share it; smooth for unseen terms).
    n_docs = max(1, len(chat_tokens))
    df: Counter = Counter()
    for toks in chat_tokens.values():
        df.update(set(toks))
    idf = {t: math.log((1 + n_docs) / (1 + d)) + 1 for t, d in df.items()}

    def vec(counts: Counter) -> dict[str, float]:
        return {t: n * idf.get(t, 1.0) for t, n in counts.items()}

    def cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(w * b[t] for t, w in a.items() if t in b)
        na = math.sqrt(sum(w * w for w in a.values()))
        nb = math.sqrt(sum(w * w for w in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    proj_vecs: dict[str, dict[str, float]] = {}
    for p in projects:
        profile = "\n".join(
            [(p.get("name") or "") * 3, p.get("description") or "",
             p.get("prompt_template") or ""]
            + [f"{d.get('filename') or ''}\n{d.get('content') or ''}"
               for d in p.get("docs") or []]
        )
        proj_vecs[(p.get("name") or "").strip()] = vec(Counter(_tokens(profile)))

    draft: dict[str, list[str]] = {name: [] for name in proj_vecs}
    rows: list[dict[str, Any]] = []
    for c in conversations:
        cv = vec(chat_tokens[c["uuid"]])
        scored = sorted(
            ((cosine(cv, pv), name) for name, pv in proj_vecs.items()), reverse=True
        )
        best_score, best = scored[0] if scored else (0.0, "")
        second = scored[1] if len(scored) > 1 else (0.0, "")
        assigned = best if best_score >= min_score else ""
        if assigned:
            draft[assigned].append(c["uuid"])
        rows.append({
            "uuid": c["uuid"], "title": c.get("name") or "(untitled)",
            "assigned": assigned, "score": round(best_score, 3),
            "runner_up": second[1], "runner_up_score": round(second[0], 3),
            "margin": round(best_score - second[0], 3),
        })
    return draft, rows


def cmd_propose_map(args) -> None:
    data = load_export(Path(args.export))
    if not data["projects"]:
        sys.exit("No projects/ in this export — nothing to score against. "
                 "(ChatGPT exports have no projects; use project_listings/ + build-map.)")
    draft, rows = propose_map(data["conversations"], data["projects"], args.min_score)
    Path(args.out).write_text(json.dumps(draft, indent=2))
    report_path = Path(args.out).with_suffix(".report.md")
    lines = [
        "# propose-map report", "",
        "Lexical draft — **review before use**. Low-margin rows are guesses.",
        "", "| assigned | score | margin | runner-up | title |",
        "|----------|-------|--------|-----------|-------|",
    ]
    for r in sorted(rows, key=lambda r: (r["assigned"] == "", -r["margin"])):
        lines.append(
            f"| {r['assigned'] or '—'} | {r['score']} | {r['margin']} "
            f"| {r['runner_up']} ({r['runner_up_score']}) "
            f"| {r['title'].replace('|', chr(92) + '|')} |"
        )
    unassigned = sum(1 for r in rows if not r["assigned"])
    lines += ["", f"_{len(rows)} chats scored; {unassigned} left unassigned "
              f"(score < {args.min_score})._"]
    report_path.write_text("\n".join(lines) + "\n")
    print(f"Draft map: {args.out} "
          f"({sum(len(v) for v in draft.values())} assigned, {unassigned} unassigned)")
    print(f"Review report: {report_path}")
    print("Next: correct the draft by hand (or with prompts/propose-map.md), "
          "then use it as your map for `prepare`.")


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


def cmd_export(args) -> None:
    """Write the export in the canonical format (FORMAT.md)."""
    data = load_export(Path(args.export))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    convs = data["conversations"]
    (out_dir / "conversations.json").write_text(
        json.dumps(convs, indent=2, ensure_ascii=False) + "\n"
    )
    print(f"Wrote {out_dir / 'conversations.json'} ({len(convs)} conversations)")
    if args.markdown:
        md_dir = out_dir / "markdown"
        md_dir.mkdir(exist_ok=True)
        index = ["# Conversation archive", ""]
        used: set[str] = set()
        for conv in sorted(convs, key=lambda c: c.get("created_at") or ""):
            slug = chat_slug(conv)
            if slug in used:
                slug = f"{slug}-{str(conv.get('uuid'))[:8]}"
            used.add(slug)
            (md_dir / f"{slug}.md").write_text(render_transcript(conv))
            index.append(f"- [{conv.get('name') or '(untitled)'}]({slug}.md) — "
                         f"{(conv.get('created_at') or '')[:10]}")
        (md_dir / "index.md").write_text("\n".join(index) + "\n")
        print(f"Wrote {len(used)} transcripts -> {md_dir}")


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


def cmd_resume(args) -> None:
    """Write a resume-primer per recently active conversation."""
    from datetime import datetime, timedelta

    def parse_ts(s: str) -> datetime | None:
        try:
            return datetime.fromisoformat((s or "").replace("Z", "+00:00"))
        except ValueError:
            return None

    data = load_export(Path(args.export))
    stamped = [(parse_ts(c.get("updated_at") or ""), c) for c in data["conversations"]]
    stamped = [(t, c) for t, c in stamped if t is not None]
    if not stamped:
        sys.exit("No parseable timestamps in this export.")
    # Cutoff is relative to the newest activity in the export, not to today —
    # the export itself may be weeks old.
    latest = max(t for t, _ in stamped)
    cutoff = latest - timedelta(days=args.days)
    active = sorted(((t, c) for t, c in stamped if t >= cutoff), reverse=True,
                    key=lambda tc: tc[0])
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    for _, conv in active:
        slug = chat_slug(conv)
        if slug in used:
            slug = f"{slug}-{conv['uuid'][:8]}"
        used.add(slug)
        msgs = conv.get("chat_messages", [])
        tail = msgs[-args.tail:]
        shown = (f"the last {len(tail)} of {len(msgs)} messages"
                 if len(tail) < len(msgs) else f"all {len(msgs)} messages")
        primer = [
            f"# Resume: {conv.get('name') or '(untitled)'}",
            f"_Last active {(conv.get('updated_at') or '')[:10]} · {shown} below_",
            "",
            "**How to use:** start a chat in your new assistant and paste "
            "everything below, prefaced with: \"This is the tail of an earlier "
            "conversation I want to continue. Read it and pick up where we "
            "left off.\" (Or distill these files first with prompts/resume.md.)",
            "",
            "---",
            "",
            render_transcript({**conv, "chat_messages": tail}).rstrip(),
        ]
        (out_dir / f"{slug}.resume.md").write_text("\n".join(primer) + "\n")
    print(f"{len(active)} active thread(s) since {cutoff.date()} "
          f"(newest activity {latest.date()}, window {args.days}d) -> {out_dir}")
    if active:
        print("Optional: distill each primer with prompts/resume.md.")


def cmd_assemble(args) -> None:
    work = Path(args.work)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((work / "manifest.json").read_text())

    max_chars = getattr(args, "max_chars", 0) or 0
    index = ["# Project knowledge index", ""]
    for proj in manifest["projects"]:
        pslug = proj["slug"]
        header = [f"# {proj['name']} — chat knowledge", ""]
        if proj.get("description"):
            header.append(proj["description"] + "\n")
        header.append(
            f"_{len(proj['chats'])} chats"
            + (f" | project created {proj['created_at'][:10]}" if proj.get("created_at") else "")
            + "_\n"
        )
        # Anchor = slug + uuid prefix so chats sharing a title link distinctly.
        anchor = {c["uuid"]: f"{slugify(c['title'])}-{c['uuid'][:8]}" for c in proj["chats"]}

        missing = []
        sections: list[tuple[dict[str, Any], str]] = []
        for c in proj["chats"]:
            brief_path = work / c["brief"]
            lines = [f'\n<a id="{anchor[c["uuid"]]}"></a>\n',
                     f"## {c['title']}",
                     f"_{c['created_at'][:10]} · chat uuid {c['uuid']}_\n"]
            if brief_path.exists():
                lines.append(demote_headings(brief_path.read_text().strip()))
            else:
                missing.append(c["brief"])
                lines.append("_(brief not yet generated)_")
            sections.append((c, "\n".join(lines)))

        # Split along chat boundaries when a size budget is set (--max-chars),
        # so no doc exceeds the destination's upload limit. Every part keeps
        # the shared header and its own contents list.
        parts: list[list[tuple[dict[str, Any], str]]] = [[]]
        size = 0
        for sec in sections:
            if max_chars and parts[-1] and size + len(sec[1]) > max_chars:
                parts.append([])
                size = 0
            parts[-1].append(sec)
            size += len(sec[1])

        for i, part in enumerate(parts, start=1):
            suffix = f"-{i}" if len(parts) > 1 else ""
            part_note = f" (part {i}/{len(parts)})" if len(parts) > 1 else ""
            doc = [header[0] + part_note] + header[1:]
            doc.append("## Contents\n")
            for c, _ in part:
                doc.append(f"- [{c['title']}](#{anchor[c['uuid']]}) — {c['created_at'][:10]}")
            doc.append("")
            doc.extend(text for _, text in part)
            doc_path = out_dir / f"{pslug}{suffix}.md"
            content = "\n".join(doc) + "\n"
            doc_path.write_text(content)
            kb_size = max(1, len(content) // 1024)
            warn = f"  ⚠ {len(missing)} brief(s) missing" if missing and i == 1 else ""
            index.append(f"- [{proj['name']}{part_note}]({pslug}{suffix}.md) — "
                         f"{len(part)} chats, {kb_size} KB{warn}")
            print(f"Assembled {proj['name']}{part_note}: {doc_path} ({kb_size} KB)"
                  + (f"  (⚠ {len(missing)} briefs missing)" if missing and i == 1 else ""))
            if max_chars and len(content) > max_chars:
                print(f"  ⚠ {doc_path.name} still exceeds --max-chars "
                      f"({len(content)} > {max_chars}): a single chat brief is "
                      "bigger than the budget.")

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

    # Portable persona: a global "about me / how to work with me" block
    # synthesized by Claude Code (prompts/persona.md) into work/_persona.md.
    persona_src = work / "_persona.md"
    if persona_src.exists():
        text = persona_src.read_text().strip() + "\n"
        (out_dir / "persona.md").write_text(text)
        words = len(text.split())
        index.append(f"- [persona.md](persona.md) — {words} words")
        print(f"Persona: {out_dir / 'persona.md'} ({words} words)"
              + ("  ⚠ long for a preferences field — consider trimming to ~500 words"
                 if words > 800 else ""))

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

    p_exp = sub.add_parser("export", help="write the canonical format (FORMAT.md)")
    p_exp.add_argument("--export", required=True)
    p_exp.add_argument("--out", default="canonical")
    p_exp.add_argument("--markdown", action="store_true",
                       help="also write a per-chat Markdown archive")
    p_exp.set_defaults(func=cmd_export)

    p_map = sub.add_parser("build-map", help="build map.json from project_listings/*.md")
    p_map.add_argument("--export", required=True)
    p_map.add_argument("--listings", default="project_listings")
    p_map.add_argument("--out", default="map.json")
    p_map.set_defaults(func=cmd_build_map)

    p_pm = sub.add_parser("propose-map",
                          help="draft map.json by scoring chats against export projects")
    p_pm.add_argument("--export", required=True)
    p_pm.add_argument("--out", default="map.draft.json")
    p_pm.add_argument("--min-score", type=float, default=0.05,
                      help="below this cosine score a chat stays unassigned")
    p_pm.set_defaults(func=cmd_propose_map)

    p_prep = sub.add_parser("prepare", help="extract transcript bundles per project")
    p_prep.add_argument("--export", required=True)
    p_prep.add_argument("--map", required=True)
    p_prep.add_argument("--out", default="work")
    p_prep.set_defaults(func=cmd_prepare)

    p_reh = sub.add_parser("rehydrate",
                           help="extract (and optionally run) document-generator "
                                "scripts to recover generated files")
    p_reh.add_argument("--export", required=True)
    p_reh.add_argument("--out", default="rehydrated")
    p_reh.add_argument("--run", action="store_true",
                       help="execute the scripts (default: extract only)")
    p_reh.add_argument("--timeout", type=int, default=120,
                       help="per-script timeout in seconds with --run")
    p_reh.set_defaults(func=cmd_rehydrate)

    p_res = sub.add_parser("resume",
                           help="write resume-primers for recently active threads")
    p_res.add_argument("--export", required=True)
    p_res.add_argument("--days", type=int, default=14,
                       help="active = updated within this many days of the "
                            "export's newest activity")
    p_res.add_argument("--tail", type=int, default=8,
                       help="how many trailing messages to include")
    p_res.add_argument("--out", default="resume")
    p_res.set_defaults(func=cmd_resume)

    p_scrub = sub.add_parser("scrub",
                             help="scan prepared transcripts for secrets/PII")
    p_scrub.add_argument("--work", default="work")
    p_scrub.add_argument("--apply", action="store_true",
                         help="redact matches in place (default: report only)")
    p_scrub.set_defaults(func=cmd_scrub)

    p_asm = sub.add_parser("assemble", help="combine briefs into docs + memory blocks")
    p_asm.add_argument("--work", default="work")
    p_asm.add_argument("--out", default="out")
    p_asm.add_argument("--max-chars", type=int, default=0, dest="max_chars",
                       help="split knowledge docs that exceed this many characters "
                            "(0 = never split; sizes are always reported)")
    p_asm.set_defaults(func=cmd_assemble)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
