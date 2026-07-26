# Prompt: sensitive-content review pass (after `synopsis.py scrub`)

The regex scrub catches machine-shaped secrets. This pass catches what only
judgment can: content a person wouldn't want uploaded into a new (often
employer-administered) account.

---

Read every `*.transcript.md` under `work/`. Flag passages in these
categories — do not rewrite anything yourself:

1. **Third parties**: named colleagues/students/clients discussed critically,
   or identifiable personal details about someone else.
2. **Employment**: salary, offers, performance reviews, disputes, resignation
   plans.
3. **Health, legal, financial**: medical questions, legal matters, account or
   ID numbers the regexes missed.
4. **Credentials in prose**: passwords or access instructions written out in
   sentences ("the wifi password is …", "log in with …").
5. **Confidential material**: anything marked internal/confidential, or
   obviously pasted from non-public documents.

Output `work/scrub-model-report.md`:

```markdown
# Model scrub report

## <relative path>
- line <n> — <category>: <one-line description> — suggested action:
  [drop passage | mask name | keep, low risk]
```

Rules: be specific enough that the user can find each passage instantly, but
do not repeat the sensitive content verbatim in the report. If a whole chat
is sensitive end-to-end, say so at the top of its section and recommend
excluding it from `prepare`/`assemble` entirely. Make no edits — the user
decides what to act on.
