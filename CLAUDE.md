# Chronicle — project context

Local-first viewer + migration toolkit for Claude/ChatGPT chat exports.
Python 3.14+, stdlib-only core; 4-space indentation, ruff (line length 100),
pytest. Dev setup: `pip install -e ".[server,docs,dev]"` then `python -m pytest`.

## Gotchas and contracts

- **`conversations-viewer.html` is a committed build artifact.** After ANY edit
  to `viewer.template.html` or `static/*.js`, run `python build_standalone.py`
  and commit both together — CI fails on drift.
- **Two viewers, one flagship.** The standalone (`viewer.template.html`) gets
  new features. The Flask UI (`templates/index.html`) is feature-frozen:
  correctness/security fixes only — and fixes to shared logic (e.g. `esc()`)
  must land in BOTH.
- **The CSP is the product.** The standalone viewer's privacy claim rests on
  its Content-Security-Policy (`connect-src 'none'`, `img-src data: blob:`).
  Never add a network request, remote asset, or CDN reference to the viewer;
  if a change touches the CSP or privacy copy, update them together.
- **Export content is untrusted input.** Everything from a loaded export goes
  through `esc()` (which escapes quotes — attribute contexts) or DOMPurify.
  Keep it that way; the viewer is designed to open other people's files.
- **One canonical schema** (FORMAT.md): readers convert INTO it
  (`chatgpt_export.py`), consumers read only it, unknown keys are ignored,
  changes are additive-only.
- **`store.py` is the query layer** over `conversations.db` — new consumers
  (like `mcp_server.py`) build on it; don't write raw SQL elsewhere.
  (`app.py` predates it and keeps its own queries.)
- **Tests import sample data**: fixtures come from `samples/build_samples.py`
  module constants — keep that module import-side-effect-free (all writes stay
  under `main()`).
- **`rehydrate --run` executes code from exports.** Keep execution strictly
  opt-in, sandboxed by timeout, and behind the printed warning.
- Personal exports and migration outputs (`*.zip`, `work/`, `out/`,
  `project_listings/`, `map.json`) are gitignored — never commit them and
  never weaken `.gitignore`.
