# Cross-chat memory synthesis

Convert ALL of a project's briefs into a single durable memory block — the
things an AI assistant should remember about the **project as a whole**, not a
chat-by-chat list. Used to produce each `<project>.memory.md` (MIGRATE.md,
Step 6).

## Rules
- Base it ONLY on the project's briefs (or its assembled knowledge document).
  Do not invent.
- Synthesize across chats: surface what recurs and what matters, not a summary
  of each chat in turn.
- If the input is large, read it in parts and prioritize the Topic and
  Decisions sections of each chat.
- Start at the `## Cross-chat synthesis` heading (no H1).

## Output structure
```
## Cross-chat synthesis

~400–800 words (longer is fine for large projects) covering:
- the major recurring themes / threads across the project;
- key facts, figures, and decisions established;
- the people, orgs, and roles involved;
- standing conclusions;
- notable open questions.

Write dense, faithful prose (bold sub-labels are fine for scanning). This is
memory, so favor durable facts over narrative.
```
