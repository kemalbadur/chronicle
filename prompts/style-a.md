# Style A — Structured Knowledge Brief

Convert ONE chat transcript into a sectioned prose brief optimized to be
uploaded as project knowledge and re-read later. This is the **default** style:
expansive and readable, preserving the substance a short memory summary drops.

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
## Topic
1–2 sentences: what the chat was about + who/what context (people, org, roles).

## Body
The substance, organized by the chat's natural structure: the questions
explored, facts established or verified (keep specifics and sourcing), and
notably how any positions or conclusions changed across the conversation.
Aim for ~2–3× the length of a short summary.

## Decisions / outcomes
What was concluded or produced.

## Open items / follow-ups
Action items or unresolved threads, if any. (Omit the section if none.)

## Key sources
URLs cited in the chat, as a list. (Omit the section if none.)
```
