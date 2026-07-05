# Sample exports

Fake-but-realistic exports so you can try Chronicle without your own data.
Every chat is invented, but the content is built around **real University of
Chicago facts** (the 1890 Rockefeller founding, Chicago Pile-1, the Core, etc.).

- **`claude/`** — a Claude-style export: 3 chats, a **project** (with custom
  instructions + two docs), and **two artifacts** (an HTML milestones timeline
  and an SVG Maroons crest).
- **`chatgpt/`** — a ChatGPT-style export (mapping-graph format): 2 chats.
  ChatGPT exports have no projects or artifacts, so there are none here.

## Try it

Build the two importable `.zip` files, then drag one into
`conversations-viewer.html`:

```sh
python samples/build_samples.py
# -> samples/claude-uchicago-sample.zip
# -> samples/chatgpt-uchicago-sample.zip
```

`build_samples.py` is the **source of truth** (all sample content is inline in
that one file). Everything it writes — the `claude/` and `chatgpt/` JSON folders
and both `.zip` files — is git-ignored regenerable output, so it isn't checked
in; run the script to produce it. After building, you can also drag the
generated `samples/claude/conversations.json` straight into the viewer and then
use **Load projects folder…** on `samples/claude/projects/`.

To change the samples, edit `build_samples.py` and re-run it.
