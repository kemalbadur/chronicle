"""resolve / resolve_row: uuid, uuid-prefix, title, and title+date matching."""
from __future__ import annotations

from synopsis import build_indexes, resolve, resolve_row, title_date_index

U1 = "11111111-1111-4111-8111-111111111111"
U2 = "11111122-2222-4222-8222-222222222222"
U3 = "33333333-3333-4333-8333-333333333333"
U4 = "44444444-4444-4444-8444-444444444444"
U5 = "55555555-5555-4555-8555-555555555555"

CONVS = [
    {"uuid": U1, "name": "Unique Chat", "updated_at": "2026-05-02T10:00:00Z"},
    {"uuid": U2, "name": "Duplicate", "updated_at": "2026-05-03T10:00:00Z"},
    {"uuid": U3, "name": "Duplicate", "updated_at": "2026-05-04T10:00:00Z"},
    {"uuid": U4, "name": "Twins", "updated_at": "2026-05-05T10:00:00Z"},
    {"uuid": U5, "name": "Twins", "updated_at": "2026-05-05T11:00:00Z"},
]
BY_UUID, BY_TITLE = build_indexes(CONVS)
BY_TD = title_date_index(CONVS)


def row(title=None, uuid=None, date=None):
    return {"title": title, "uuid": uuid, "date": date}


def test_resolve_row_by_uuid():
    conv, note = resolve_row(row(uuid=U1), BY_UUID, BY_TITLE, BY_TD)
    assert conv["uuid"] == U1 and note == "uuid"


def test_resolve_row_uuid_not_in_export():
    conv, note = resolve_row(
        row(uuid="99999999-9999-4999-8999-999999999999"), BY_UUID, BY_TITLE, BY_TD)
    assert conv is None and "not in export" in note


def test_resolve_row_unique_title():
    conv, note = resolve_row(row(title="Unique Chat"), BY_UUID, BY_TITLE, BY_TD)
    assert conv["uuid"] == U1 and note == "title"


def test_resolve_row_duplicate_title_date_disambiguates():
    conv, note = resolve_row(
        row(title="Duplicate", date="2026-05-04"), BY_UUID, BY_TITLE, BY_TD)
    assert conv["uuid"] == U3 and note == "title+date"


def test_resolve_row_duplicate_title_same_date_still_ambiguous():
    conv, note = resolve_row(
        row(title="Twins", date="2026-05-05"), BY_UUID, BY_TITLE, BY_TD)
    assert conv is None and "AMBIGUOUS" in note


def test_resolve_row_duplicate_title_without_date():
    conv, note = resolve_row(row(title="Duplicate"), BY_UUID, BY_TITLE, BY_TD)
    assert conv is None and "AMBIGUOUS" in note


def test_resolve_row_unmatched_title():
    conv, note = resolve_row(row(title="No Such Chat"), BY_UUID, BY_TITLE, BY_TD)
    assert conv is None and "UNMATCHED" in note


def test_resolve_full_uuid_and_exact_title():
    assert resolve(U1, BY_UUID, BY_TITLE)[1] == "uuid"
    assert resolve("Unique Chat", BY_UUID, BY_TITLE)[0]["uuid"] == U1


def test_resolve_uuid_prefix_unique_and_ambiguous():
    conv, note = resolve("11111111", BY_UUID, BY_TITLE)
    assert conv["uuid"] == U1 and note == "uuid-prefix"
    conv, note = resolve("111111", BY_UUID, BY_TITLE)
    assert conv is None and "AMBIGUOUS uuid prefix" in note


def test_resolve_ambiguous_title_and_unmatched():
    conv, note = resolve("Duplicate", BY_UUID, BY_TITLE)
    assert conv is None and "AMBIGUOUS title" in note
    conv, note = resolve("No Such Chat", BY_UUID, BY_TITLE)
    assert conv is None and "UNMATCHED" in note
