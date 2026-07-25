# Prompt: portable persona — a global "about me / how to work with me" block

Run this over the whole history (all `work/**/*.transcript.md`, or the
Markdown archive from `synopsis.py export --markdown`), not per project.
Write the result to `work/_persona.md`; `assemble` will copy it to
`out/persona.md`.

---

You are distilling one person's entire AI-conversation history into a
portable persona block they can paste into a new assistant's preferences or
custom instructions. Mine for what is *durable and cross-cutting* — ignore
one-off task content.

Collect evidence for:

1. **Who they are**: role, field, institution, projects/domains they return
   to, tools and stack they actually use.
2. **How they want answers**: length, tone, formatting habits they reward;
   and every correction they've given an assistant ("be concise", "no
   emojis", "stop hedging", "ask before assuming") — these are gold; quote
   the pattern, not the chat.
3. **Recurring context**: constraints that keep coming up (privacy stance,
   platform, budget, time zone, writing voice for drafts).
4. **Anti-preferences**: things that visibly annoyed them.

Output `work/_persona.md`, under 500 words, in this shape:

```markdown
# About me
<3-6 tight bullets: role, domains, stack>

# How to work with me
<5-10 bullets, each a directly actionable instruction an assistant can obey>

# Recurring context
<2-5 bullets>
```

Rules: only include what at least two separate conversations support; no
sensitive personal details (health, finances, third parties) — this block
will be pasted into other services; write instructions in the imperative,
addressed to the assistant.
