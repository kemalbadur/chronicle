# Chronicle

A local toolkit for your exported **Claude** or **ChatGPT** history. Everything
runs on your own machine — your data never leaves your device unless you choose
to upload it. Two things it does:

1. **View** — a threaded, full-text-searchable viewer for browsing your export.
2. **Migrate** — turn your history into per-project knowledge documents +
   memory blocks you can load into **Claude Enterprise** (or anywhere else).
   See **[MIGRATE.md](MIGRATE.md)** for the step-by-step guide. *(Requires
   [Claude Code](https://claude.com/claude-code), which does the summarizing.)*

**Just want to see it?** Run `python samples/build_samples.py` to generate two
fake, UChicago-themed sample exports (Claude + ChatGPT — with chats, a project,
and artifacts) and drag one into the viewer. See **[samples/](samples/)**.

---

## Viewer

A local, threaded, full-text-searchable viewer for your exported **Claude** or
**ChatGPT** history. Everything runs in your browser — your data never leaves
your device.

There are two ways to run it:

- **Standalone single file** (`conversations-viewer.html`) — no install, no
  server, runs entirely in the browser. This is the version to **share with
  other people** so they can browse their own exports. See below.
- **Local server** (`app.py`) — the original Flask + SQLite version, best for
  very large exports. Documented further down.

---

## Standalone single-file viewer (shareable)

`conversations-viewer.html` is fully self-contained: open it in any browser,
choose your Claude or ChatGPT export, and everything (parsing, search,
threading, Markdown) happens locally. **Your data never leaves your device** —
no upload, no server, works offline. The only file a recipient needs is that
one HTML file.

### For an end user

1. Download your data:
   - **Claude:** Settings → Privacy → Export data.
   - **ChatGPT:** Settings → Data controls → Export data.

   Either way you'll get a `.zip` by email.
2. Open `conversations-viewer.html` in any modern browser (double-click).
3. Drag the `.zip` anywhere on the page, or click **Choose export…**. Chronicle
   detects whether it's a Claude or ChatGPT export automatically.

That's it — no Python, no install, no internet.

#### Projects

The viewer has a **Chats / Projects** tab switcher. The downloadable export
zip only contains conversations, **not** projects — projects come as a separate
`projects/` folder (one JSON file per project, each with the project's
instructions and documents). To view them, click **Load projects folder…** on
the landing screen (or the Projects tab) and pick that `projects/` folder. Each
project shows its instructions (rendered Markdown) and its documents (expandable,
loaded on demand since some hold large extracted text). If a future export zip
ever bundles `projects/*.json`, the viewer ingests those automatically too.

#### ChatGPT exports

Chronicle reads ChatGPT exports too — drag the whole `.zip` and the format is
detected automatically. A few differences from Claude:

- ChatGPT splits conversations across several files (`conversations-000.json`,
  `conversations-001.json`, …); Chronicle merges them on load.
- **Images** you sent or that ChatGPT generated are decoded from the export's
  asset files (`*.dat`, mapped via `conversation_asset_file_names.json`) and
  shown inline in the conversation.
- The reply tree is rebuilt from each message's `parent` pointer; hidden
  system/empty nodes are skipped.
- Conversation dates come from the message timestamps (ChatGPT sometimes stamps
  a chat's top-level date with the export date instead of the real one).
- ChatGPT exports have **no projects or artifacts**, so those tabs stay empty
  for them, and the assistant is labeled "ChatGPT" rather than "Claude".

### To build it (for the person packaging/sharing)

```sh
python build_standalone.py    # inlines the vendored libs -> conversations-viewer.html
```

The build inlines three vendored libraries from `static/` into the single
output file: `marked` (Markdown), `DOMPurify` (sanitizing), and `fflate`
(reading the export `.zip` directly). Search is a pure in-browser scan, so
there's no SQLite/WASM dependency. Note: very large exports (100 MB+) are
parsed in memory on load, which takes a few seconds and some RAM.

---

## Migrate: summarize your projects into a new account

Chronicle can turn an export into per-project **knowledge documents** and
**memory blocks** — Claude-written summaries of every chat — that you upload
into a fresh Claude Enterprise account (or any other tool). A Claude export
has every chat but no record of which chats belonged to which project, so
there's one manual step (you map chats → projects); the rest is automated.

The pipeline (full walkthrough in **[MIGRATE.md](MIGRATE.md)**):

1. **`list`** — dump every chat in the export to review it.
2. **map** — tell the tool which chats belong to which project (via
   `project_listings/`), then **`build-map`** resolves them.
3. **`prepare`** — extract one full transcript per chat.
4. **briefs** — Claude Code summarizes each transcript into a `.brief.md`
   (pick a style in `prompts/`).
5. **synthesis** — Claude Code writes a cross-chat memory block per project.
6. **`assemble`** — produces `out/<project>.md` (knowledge doc) and
   `out/<project>.memory.md` (memory) per project.

Then, in the new account: create the project, upload `<project>.md` as project
knowledge, and paste `<project>.memory.md` into its instructions. The
summarizing runs in your own Claude Code — nothing is uploaded until you import
it. *(Requires [Claude Code](https://claude.com/claude-code).)*

---

## Local server version

## Setup

```sh
pip install -r requirements.txt
python build_index.py        # builds conversations.db (~38 MB, <1s)
python app.py                # serves http://127.0.0.1:5050
```

Open http://127.0.0.1:5050.

Re-run `build_index.py` whenever `conversations.json` changes. Set a
different port with `PORT=8000 python app.py` (5000 is taken by macOS
AirPlay Receiver).

## What the viewer does

- **Sidebar** lists every conversation; sort by recent / oldest / title.
- **Search** runs SQLite FTS5 full-text search across all message bodies,
  thinking blocks, and attachment text. Results are ranked, show a hit
  count per conversation, and a highlighted snippet. Last word is treated
  as a prefix (`embed` matches `embedding`).
- **Threaded view** reconstructs the reply tree from `parent_message_uuid`.
  Linear chats render flat; conversations that actually branch (44 of them)
  show each branch indented under a `branch N` rail and are tagged
  `⑂ branched thread`.
- **Chat-bubble layout**: your messages align right, Claude's align left
  (texting-app style).
- **Markdown rendering**: message bodies and thinking blocks are rendered as
  Markdown (headers, lists, tables, fenced code) via `marked`, sanitized with
  `DOMPurify`. Both are vendored under `static/` so the app works offline.
- Per message: assistant **thinking** is collapsible, **tool** calls
  (`web_search`, etc.) show as chips, search terms are highlighted in the body
  (highlighting skips code blocks).
- **Artifacts, generated files, and uploaded documents** are shown as their own
  in-bubble cards:
  - **Artifacts** Claude built (🧩) and **files Claude created** (📄) render by
    type: Markdown as formatted text, **HTML in a sandboxed iframe** (with a
    *View source* toggle), **SVG as an image**, everything else as code.
  - Any card shown as **raw code** carries a short explanation that it's the
    stored code, not the rendered result, and a **📋 Copy** button — paste it
    into a new Claude chat and say "Run this" to recreate the output.
    **Document-generator scripts** (Node `docx`/`pptxgenjs`/Excel, Python
    `python-docx`/`reportlab`, etc.) get a more specific version naming the file
    type, since the rendered Word/Excel/PDF is the program's *output* and **is
    not in Anthropic's export** — only the generating code is.
  - **Uploaded documents** (📎) with extracted text are collapsible; uploads
    whose content isn't in the export are shown as a labeled reference.
  All of this content is included in the search index.
- A one-time **overview banner** appears atop the first conversation you open,
  summarizing the raw-content situation. Dismissing it ("Got it") is remembered
  across sessions (`localStorage`).
- The **Projects** view has the same treatment: its own one-time overview
  banner, a **📋 Copy** button on the project instructions, and document cards
  with a Copy button plus a note that the text is extracted (the original file
  isn't in the export). Markdown/HTML/SVG project documents render in place.
- **Deep links**: the URL reflects state, e.g.
  `/?q=minitel&open=<conversation-uuid>` — shareable and reloadable.

## Files

| File | Purpose |
|---|---|
| `build_index.py` | Parses the JSON export into `conversations.db` (SQLite + FTS5). |
| `app.py` | Flask server: `/`, `/api/conversations`, `/api/search`, `/api/conversation/<uuid>`, `/api/stats`. |
| `templates/index.html` | Single-page UI (no build step). |
| `synopsis.py` | Migration tool: `list` / `build-map` / `prepare` / `assemble` (see [MIGRATE.md](MIGRATE.md)). |
| `prompts/` | Copy-paste prompts: capture a project's chat list, and the brief/synthesis styles. |
| `build_userguide.py` | Generates the Word user guide, "Chronicle - User Guide.docx". |

The export itself (`conversations.json`), the generated `conversations.db`, and
all migration inputs/outputs (`project_listings/`, `map.json`, `work/`, `out/`)
are git-ignored and not meant to be committed.
