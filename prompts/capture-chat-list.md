# Capture a project's chat list

Use this to produce the `project_listings/<Project Name>.md` file that
`synopsis.py build-map` reads (see MIGRATE.md, Step 2).

**How to use**
1. On claude.ai (or ChatGPT), open the **project** whose chats you want to
   capture and start a **new chat inside that project**.
2. Paste the prompt below (fill in the project name).
3. Copy the Markdown code block it returns and save it as
   `project_listings/<Project Name>.md` — the file name must match the
   project's name **exactly** (so the tool can attach the project's
   description and memory later).
4. Repeat for each project.

> The assistant can only enumerate chats it can see in the current project.
> For a big project it may need to page through results — the prompt tells it
> to keep going and to flag if it couldn't reach them all. Cross-check the
> count against `python synopsis.py list --export your-export.zip`.

---

## Prompt

```
I'm exporting this project's chats to migrate them into another account.
List EVERY conversation in THIS project — only this project, not chats
outside it and not other projects.

Return your answer as a SINGLE Markdown code block and nothing before or
after it, so I can save it straight to a file. Use exactly this structure:

# <Project Name>

| Date | Title | Link |
|------|-------|------|
| YYYY-MM-DD | <exact chat title> | <chat URL if you can provide one> |

Rules:
- One row per conversation, newest first.
- Date = the chat's last-updated date, formatted YYYY-MM-DD.
- Title = the chat's title copied EXACTLY as it appears (don't rephrase).
- Link = the conversation's URL if available (Claude: https://claude.ai/chat/<id>;
  ChatGPT: https://chatgpt.com/c/<id>). If you can't get it, leave the cell blank.
- Include ALL conversations. If they come back in pages, keep going until
  every one is listed.
- Put nothing inside the code block except the heading and the table.

If you cannot retrieve the complete list, say so in one line AFTER the code
block and include as many rows as you could confirm.
```
