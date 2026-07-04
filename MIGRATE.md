# Migrate your Claude / ChatGPT history into Claude Enterprise

Turn an exported chat history into per-project **knowledge documents** and
**memory blocks** you can load into a new Claude Enterprise account (or any
other tool). Everything runs locally on your machine and in your own Claude
Code — nothing is uploaded until *you* import it.

## What you need

- **Claude Code** (this does the summarizing — required)
- **Python 3.11+**
- Your **data export** (`.zip`) from Claude and/or ChatGPT
- This repo (`git clone …`)

## The one thing to understand first

A Claude export contains **every chat, but no record of which chats belonged to
which project.** So there's exactly one manual step: you tell the tool which
chats go with which project (Step 2). Everything else is automated.

---

## Step 1 — Get your export

- **Claude:** Settings → Privacy → **Export data**
- **ChatGPT:** Settings → Data controls → **Export data**

You'll receive a `.zip` by email. Drop it in the repo folder. (Optional: open
`conversations-viewer.html` in any browser and drag the zip in to browse/search
your history first — fully local.)

## Step 2 — List each project's chats

For each project, capture its chat list into `project_listings/<Project Name>.md`.
The easy way: open the project on claude.ai (or ChatGPT), start a new chat
inside it, and paste the prompt in [`prompts/capture-chat-list.md`](prompts/capture-chat-list.md).
Save what it returns as `project_listings/<Project Name>.md` — **the file name
must match the project's name exactly** so the tool can attach that project's
description and memory later.

To see everything in your export while building/checking these lists:

```bash
python synopsis.py list --export your-export.zip --out all-chats.md
```

> Don't care about per-project structure? See the "one big file" note at the bottom.

## Step 3 — Build the map

```bash
python synopsis.py build-map --export your-export.zip --listings project_listings --out map.json
```

Open `map.report.md`. It flags anything it couldn't match uniquely (usually two
chats sharing a title). Fix those by putting the exact chat URL in your listing,
then re-run. When the report is clean, you're set.

## Step 4 — Extract the transcripts

```bash
python synopsis.py prepare --export your-export.zip --map map.json --out work
```

This writes one full transcript per chat under `work/<project>/`.

## Step 5 — Generate the briefs (Claude Code)

First pick a summary **style** (one brief per chat):

| Style | File | Best for |
|---|---|---|
| **A — Structured Knowledge Brief** (default) | `prompts/style-a.md` | A readable knowledge doc you'll re-read |
| **B — Chronological Digest** | `prompts/style-b.md` | When *how the thinking evolved* matters |
| **C — Decision & Artifact Log** | `prompts/style-c.md` | Terse, extractable, checklist-style |

Open **Claude Code** in the repo folder and paste (swap in your chosen style file):

```
For every file matching work/*/*.transcript.md, read it and write a knowledge
brief to the same path but ending .brief.md instead of .transcript.md. Follow
prompts/style-a.md exactly. Work through them in parallel batches. Use ONLY the
transcript — do not invent anything.
```

Claude Code fans out and writes a `.brief.md` next to each transcript. (You can
mix styles per project by running the prompt per folder with a different style
file.)

## Step 6 — Synthesized memory blocks (Claude Code, optional but recommended)

Still in Claude Code, paste:

```
For each project folder under work/, read all its *.brief.md files and write a
_synthesis.md in that folder, following prompts/synthesis.md — a cross-chat
memory synthesis (themes, key facts, people, decisions, open questions). Base it
only on the briefs.
```

## Step 7 — Assemble the deliverables

```bash
python synopsis.py assemble --work work --out out
```

You now have, in `out/`:
- `<project>.md` — the full knowledge document (a brief per chat, with a table of contents)
- `<project>.memory.md` — the memory block (synthesis + folded-chat index)
- `index.md` — links to every project

## Step 8 — Import into Claude Enterprise (or anywhere)

For each project, in your new account:
1. **Create the project.**
2. Upload **`out/<project>.md`** as **project knowledge** (a document).
3. Paste **`out/<project>.memory.md`** into the project's custom instructions / memory.

The files are plain Markdown, so the same documents work as knowledge/context in
any other tool.

---

### Notes

- **Privacy:** the viewer runs entirely in your browser; the CLI runs on your
  machine; the summarizing runs in your Claude Code. Your data leaves only when
  you upload it in Step 8. Your export, `map.json`, `project_listings/`, `work/`,
  and `out/` are all git-ignored so they never get committed.
- **Completeness check:** the in-project assistant (Step 2) can only list chats
  it can retrieve, and may paginate; always cross-check its count against
  `python synopsis.py list`.
- **Large projects:** a project with 100+ chats produces a big document — fine
  as an uploaded file, but you can split it per chat if a size limit gets in the way.
- **Simpler "one file" path:** skip Steps 2–3, put every chat under a single
  listing (or one project in `map.json`), and you'll get one combined knowledge
  file instead of per-project docs.
