"""Assemble the standalone, single-file Chronicle conversation viewer.

Inlines the vendored JS libraries (fflate, marked, DOMPurify) into
viewer.template.html and writes a self-contained conversations-viewer.html
that runs entirely in the browser — no server, no install, no internet.

Run: python build_standalone.py
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).parent
TEMPLATE = HERE / "viewer.template.html"
STATIC = HERE / "static"
OUT = HERE / "conversations-viewer.html"

# token in the template -> vendored file to inline
LIBS = {
    "/*__FFLATE__*/": STATIC / "fflate.min.js",
    "/*__MARKED__*/": STATIC / "marked.min.js",
    "/*__PURIFY__*/": STATIC / "purify.min.js",
}


def main() -> None:
    html = TEMPLATE.read_text()
    for token, path in LIBS.items():
        if token not in html:
            raise SystemExit(f"Template is missing token {token}")
        code = path.read_text()
        # Guard against an inlined library prematurely closing the <script>.
        code = code.replace("</script", "<\\/script")
        html = html.replace(token, code)
    OUT.write_text(html)
    size_mb = OUT.stat().st_size / 1_000_000
    print(f"Wrote {OUT.name} ({size_mb:.1f} MB) — open it in any browser.")


if __name__ == "__main__":
    main()
