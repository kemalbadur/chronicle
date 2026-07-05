# Style C — Decision & Artifact Log

Convert ONE chat transcript into a terse, structured, extractable record.
Choose this when you want maximum signal density and easy scanning/scripting —
it doubles well as raw material for a memory block. Least readable as prose,
most useful as a checklist/database.

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
Use short bullets, not paragraphs. Omit any subsection that is genuinely empty.
```
## Decision & artifact log

### Facts established (verified)
- <fact> — <source/how verified, if the chat states one>

### Decisions
- <what was decided, and why if the chat gives a reason>

### Action items / follow-ups
- [ ] <who> — <what>

### Artifacts produced
- <drafts, documents, code, diagrams the chat generated>

### Profile signals
- <stated preferences, working style, or standing constraints the user revealed>

### Key sources
- <URL> — <what it supports>
```
