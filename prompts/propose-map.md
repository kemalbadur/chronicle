# Prompt: review / produce a chat-to-project map with Claude Code

Use this after `python synopsis.py propose-map` (to review its draft), or on
its own when the lexical draft isn't good enough.

---

You are mapping chats from an exported AI-conversation history to the
projects they belonged to. You have:

- `map.draft.json` and `map.draft.report.md` — a lexical first draft with
  scores and margins (if propose-map was run),
- the output of `python synopsis.py list --export EXPORT.zip --out all-chats.md`,
- the project names and descriptions (from the export's `projects/` folder or
  the user's description).

For each chat, decide which project it belongs to, or `unassigned` if none
fits. Rules:

1. Trust high-margin draft rows; scrutinize rows with margin < 0.05 and
   everything unassigned.
2. Judge by what the chat is *about*, not shared vocabulary — a chat that
   merely mentions a project name in passing does not belong to it.
3. When unsure between two projects, leave the chat unassigned and say why in
   one line. Do not force assignments.
4. Output `map.json` in exactly this shape (uuids only):

```json
{
  "Project Name": ["uuid", "uuid"],
  "Another Project": ["uuid"]
}
```

5. After the JSON, list every chat you left unassigned with a one-line reason.
