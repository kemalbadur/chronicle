# The Chronicle canonical format

Chronicle normalizes every supported chat export into one schema — the shape
Anthropic's Claude export already uses, minimally extended. Every reader
(Claude zip, ChatGPT zip) is a converter *into* this format; every feature
(viewer, index, migration pipeline, MCP server) consumes only this format.
Adding a new source or destination is therefore a one-sided problem.

Produce it from any supported export with:

```sh
python synopsis.py export --export EXPORT.zip --out canonical/            # conversations.json
python synopsis.py export --export EXPORT.zip --out canonical/ --markdown # + per-chat .md archive
```

## conversations.json

A JSON array of conversation objects:

```jsonc
[
  {
    "uuid": "string, unique",            // ChatGPT: conversation_id
    "name": "string",                    // "(untitled)" if absent
    "summary": "string, may be empty",   // Claude-only; "" otherwise
    "created_at": "ISO-8601 or \"\"",
    "updated_at": "ISO-8601 or \"\"",
    "source": "claude | chatgpt",        // absent means claude (legacy exports)
    "chat_messages": [ <message>, ... ]  // chronological
  }
]
```

### message

```jsonc
{
  "uuid": "string, unique within the conversation",
  "text": "",                            // legacy plain-text fallback for content
  "content": [ <block>, ... ],
  "sender": "human | assistant",
  "created_at": "ISO-8601 or \"\"",
  "parent_message_uuid": "uuid of parent, or the root sentinel",
  "attachments": [                       // uploads whose text IS in the export
    { "file_name": "...", "file_type": "...", "extracted_content": "..." }
  ],
  "files": [                             // uploads/images with NO content in the export
    { "file_name": "..." }
  ],
  "no_response": true                    // optional; a ChatGPT Deep Research prompt
                                         // whose result is not in the export
}
```

The root sentinel for `parent_message_uuid` is
`00000000-0000-4000-8000-000000000000`. A conversation *branches* when two
messages share a parent; readers must preserve `parent_message_uuid` so
branch structure survives.

### block

```jsonc
{ "type": "text",     "text": "markdown" }
{ "type": "thinking", "text": "markdown" }          // reasoning, collapsible in viewers
{ "type": "tool_use", "name": "artifacts",          // an artifact Claude built
  "input": { "id": "...", "type": "text/html", "title": "...",
             "command": "create|update|rewrite", "content": "...", "new_str": "..." } }
{ "type": "tool_use", "name": "create_file",        // a file Claude wrote
  "input": { "path": "...", "file_text": "..." } }
{ "type": "tool_use", "name": "<other tool>", "input": { } }  // shown as a chip/name only
```

Converters map source-specific content into these blocks. The ChatGPT reader,
for example, renders `code` / `execution_output` content as fenced `text`
blocks and `thoughts` / `reasoning_recap` as `thinking` blocks
(see `chatgpt_export.py`).

## Markdown archive (`--markdown`)

`export --markdown` additionally writes one `<date>-<slug>.md` per
conversation (the same faithful transcript rendering the migration pipeline
uses: bodies, thinking, artifacts and created files in overflow-proof fences,
attachment text, tool names) plus an `index.md`. This is the human-readable,
chatbot-agnostic cold-storage variant.

## Stability

- Additive changes only; consumers must ignore unknown keys.
- `uuid`, `name`, `chat_messages[].uuid/sender/content/parent_message_uuid`
  are required; everything else may be empty or absent.
