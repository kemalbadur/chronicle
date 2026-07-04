# Style B — Chronological Digest

Convert ONE chat transcript into a turn-by-turn walkthrough that follows the
conversation's arc. Choose this when *how the thinking evolved* matters more
than the final conclusions — debugging sessions, negotiations, drafts that went
through several revisions, arguments where positions shifted.

## Shared rules (all styles)
- Use ONLY the transcript. Do not invent facts.
- Preserve specifics: names, numbers, dates, decisions, draft/artifact content.
- Carry through the important URLs/sources the chat cites.
- The transcript may include an "Export's own (memory-style) summary" blockquote
  near the top and `[thinking]` sections — use them as context, but the
  **messages are the source of truth**.
- Do NOT emit a top-level `#` H1 title (the assembler adds one). Start at the
  first `##` heading below.

## Output structure
```
## Chronological digest

A compact, ordered walkthrough of the conversation. Group the messages into
the natural exchanges/turns and, for each, capture in a sentence or two:
- what was asked or proposed, and
- what was answered or decided —
explicitly noting **how positions changed**: corrections, reversals,
concessions, and pushback. Keep concrete specifics (names, figures, quotes).

Use a short bold lead per turn to keep it scannable, e.g.:
**Turn 3 — <who> pushed back:** … **Response:** …

## Outcome
One short paragraph: where the conversation landed and what it produced.
(Omit if the digest already makes this obvious.)

## Key sources
URLs cited in the chat, as a list. (Omit the section if none.)
```
