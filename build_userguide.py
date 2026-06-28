"""Generate a Word (.docx) user guide for the Claude Conversation Viewer.

Run: python build_userguide.py
Produents: "Claude Viewer - User Guide.docx"
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

ACCENT = RGBColor(0xB8, 0x55, 0x2A)   # terracotta, matches the viewer
INK = RGBColor(0x2B, 0x2A, 0x27)
MUTED = RGBColor(0x6B, 0x66, 0x60)
OUT = Path(__file__).parent / "Claude Viewer - User Guide.docx"


def main() -> None:
    doc = Document()

    # Base font
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.font.color.rgb = INK

    # ---- Title ----
    title = doc.add_paragraph()
    run = title.add_run("Browsing Your Claude History")
    run.font.size = Pt(26)
    run.font.bold = True
    run.font.color.rgb = ACCENT
    sub = doc.add_paragraph()
    r = sub.add_run("A simple guide to opening and searching your exported Claude data")
    r.font.size = Pt(13)
    r.font.color.rgb = MUTED
    doc.add_paragraph()

    def h(text: str) -> None:
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.font.size = Pt(15)
        run.font.bold = True
        run.font.color.rgb = ACCENT
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)

    def body(text: str) -> None:
        p = doc.add_paragraph(text)
        p.paragraph_format.space_after = Pt(6)

    def step(num: int, lead: str, rest: str) -> None:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(8)
        n = p.add_run(f"{num}.  ")
        n.font.bold = True
        n.font.color.rgb = ACCENT
        b = p.add_run(lead + " ")
        b.font.bold = True
        p.add_run(rest)

    def bullet(lead: str, rest: str = "") -> None:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(3)
        if lead:
            b = p.add_run(lead + (" " if rest else ""))
            b.font.bold = True
        if rest:
            p.add_run(rest)

    def note(label: str, text: str) -> None:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(6)
        lab = p.add_run(label + "  ")
        lab.font.bold = True
        lab.font.color.rgb = ACCENT
        t = p.add_run(text)
        t.font.italic = True
        t.font.color.rgb = MUTED

    # ---- Intro ----
    body(
        "You have received a viewer file named conversations-viewer.html and a .zip "
        "file containing your Claude data. The viewer lets you read and search your "
        "past Claude conversations and projects in a familiar, chat-style layout. "
        "It runs entirely in your web browser."
    )
    note(
        "Your data stays private.",
        "Everything happens on your own computer. Nothing is uploaded, there is no "
        "server, and it works without an internet connection. Your data never leaves "
        "your device.",
    )

    # ---- Getting started ----
    h("Getting started")
    step(1, "Save both files together.",
         "Put conversations-viewer.html and your .zip file in the same folder (for "
         "example, your Desktop). You do not need to unzip anything.")
    step(2, "Open the viewer.",
         "Double-click conversations-viewer.html. It opens in your default web "
         "browser (Chrome, Safari, Edge, or Firefox all work).")
    step(3, "Load your data.",
         "Drag your .zip file anywhere onto the page, or click the “Choose export…” "
         "button and select the .zip. Your conversations (and any projects) load "
         "automatically.")
    step(4, "Start browsing.",
         "Your conversations appear in the list on the left, newest first. Click any "
         "one to read it.")
    note(
        "Large files take a moment.",
        "If your history is big, give it a few seconds to load after you select the "
        "file — it is reading everything on your computer.",
    )

    # ---- Finding things ----
    h("Finding a conversation")
    bullet("Search:", "Type in the search box at the top left to search across every "
           "message. Matches are highlighted, and each result shows how many times "
           "your term appears.")
    bullet("Sort:", "Use the “sort” dropdown to order the list by most recent, oldest "
           "first, or title.")
    bullet("Open:", "Click a conversation to read the full back-and-forth. Your "
           "messages appear on the right, Claude’s on the left.")

    # ---- Projects ----
    h("Projects")
    body(
        "If you used Projects in Claude, switch to the “Projects” tab at the top of "
        "the left panel. Your projects load from the same .zip file. Each project "
        "shows its custom instructions and its documents. Click a document to expand "
        "it and read the text."
    )

    # ---- Artifacts and generated files ----
    h("Things Claude made for you")
    body(
        "When Claude created an artifact or a file, it appears inside the "
        "conversation as its own card:"
    )
    bullet("Documents, web pages, and diagrams", "render so you can read them directly.")
    bullet("A “Copy” button", "appears on every card so you can grab the content.")
    body(
        "Some cards show computer code rather than a finished document. This is "
        "normal and expected — see the next section."
    )

    # ---- What you'll see / important to understand ----
    h("Why some things look like raw code")
    body(
        "When Claude produced a Word, Excel, PowerPoint, or PDF file, your export "
        "stores the code Claude wrote to generate that file — not the finished file "
        "itself. So you will see code instead of the polished document."
    )
    body("To get the finished document back:")
    step(1, "Click the “Copy” button", "on the card.")
    step(2, "Open a new chat at claude.ai,", "paste what you copied, and send the "
         "message “Run this.”")
    step(3, "Claude regenerates the file", "for you to download.")

    # ---- What's included ----
    h("What is and isn’t in your export")
    bullet("Included:", "all your conversations, Claude’s answers, project "
           "instructions, and the extracted text of documents you or Claude worked with.")
    bullet("Not included:", "the original copies of files you uploaded, and the "
           "finished documents Claude generated. The export keeps the text and the "
           "code, but not the original or final files themselves.")

    # ---- Tips ----
    h("Tips and troubleshooting")
    bullet("Nothing happens when I drag the file:", "use the “Choose export…” button "
           "instead — it always works.")
    bullet("I want to look at a different export:", "click “↻ load another” at the top "
           "left and pick a different .zip.")
    bullet("The info banner:", "the note at the top of a conversation can be dismissed "
           "with “Got it” and won’t come back.")
    bullet("It looks empty:", "make sure you selected the .zip file you were given, "
           "not an unzipped folder.")

    doc.add_paragraph()
    closing = doc.add_paragraph()
    c = closing.add_run("That’s it — open the viewer, load your zip, and explore.")
    c.font.italic = True
    c.font.color.rgb = MUTED

    doc.save(OUT)
    print(f"Wrote {OUT.name}")


if __name__ == "__main__":
    main()
