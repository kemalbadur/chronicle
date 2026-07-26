# Prompt: distill resume-primers into "where we left off" briefings

Run after `python synopsis.py resume` has written `resume/*.resume.md`
(each holds a raw transcript tail).

---

For each `*.resume.md`: read the transcript tail below the `---` and replace
it (keep the file's title and "Last active" line) with a briefing the user
can paste as the *first message* of a new chat:

```markdown
**Context:** <2-4 sentences: what this conversation is about and what has
been established so far — decisions, constraints, facts worked out.>

**Where we left off:** <1-2 sentences: the open question or task in flight.>

**Continue by:** <the actual next message, written in the user's voice,
ready to send — e.g. "We were drafting X and had settled on Y; please
continue with Z.">
```

Rules: only use what's in the transcript — no invented state; keep each
briefing under 200 words; if the thread actually concluded (question fully
answered, nothing in flight), replace the body with `_This thread looks
finished — nothing to resume._` so the user can skip it.
