"""parse_listing / _to_iso: markdown tables and numbered lists."""
from __future__ import annotations

from synopsis import _to_iso, parse_listing


def write(tmp_path, text):
    p = tmp_path / "listing.md"
    p.write_text(text)
    return p


def test_to_iso_passthrough_and_month_names():
    assert _to_iso("2026-05-02") == "2026-05-02"
    assert _to_iso("May 6, 2026") == "2026-05-06"
    assert _to_iso("September 3, 2025") == "2025-09-03"
    assert _to_iso("yesterday") is None
    assert _to_iso("13/05/2026") is None


def test_table_any_column_order(tmp_path):
    rows = parse_listing(write(tmp_path, """\
| # | Title | Date |
|---|-------|------|
| 1 | Founding of the university | May 2, 2026 |
| 2026-05-06 | 2 | Chicago Pile-1 discussion |
"""))
    assert [r["title"] for r in rows] == [
        "Founding of the university", "Chicago Pile-1 discussion"]
    assert [r["date"] for r in rows] == ["2026-05-02", "2026-05-06"]
    assert all(r["uuid"] is None for r in rows)


def test_table_skips_urls_and_extracts_uuid(tmp_path):
    uuid = "0199d8f2-0ad6-72ff-9cc2-e7d20170b202"
    rows = parse_listing(write(tmp_path, f"""\
| Chat about econ | https://claude.ai/chat/{uuid} | 2026-05-06 |
"""))
    assert len(rows) == 1
    assert rows[0]["uuid"] == uuid
    assert rows[0]["date"] == "2026-05-06"


def test_numbered_list_with_em_dash(tmp_path):
    rows = parse_listing(write(tmp_path, "3. Maroons crest — 2026-05-09\n"))
    assert rows == [{"title": "Maroons crest", "uuid": None, "date": "2026-05-09"}]


def test_bare_uuid_line(tmp_path):
    uuid = "0199d8f2-0ad6-72ff-9cc2-e7d20170b202"
    rows = parse_listing(write(tmp_path, f"{uuid}\n"))
    assert rows == [{"title": None, "uuid": uuid, "date": None}]


def test_prose_and_header_lines_yield_no_rows(tmp_path):
    rows = parse_listing(write(tmp_path, """\
Some introductory prose without identifiers.
| Title | Date |
|-------|------|
"""))
    assert rows == []


def test_longest_cell_wins_as_title(tmp_path):
    # Documented caveat: the longest candidate cell is assumed to be the title.
    rows = parse_listing(write(tmp_path,
        "| short | a much longer notes column that steals the title | 2026-01-01 |\n"))
    assert rows[0]["title"] == "a much longer notes column that steals the title"
