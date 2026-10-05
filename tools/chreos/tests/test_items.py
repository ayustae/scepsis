from chreos.items import load_item, load_items
from chreos.model import Kind

VALID = """\
---
name: a
title: A
status: active
created: 2026-09-20T09:00:00+02:00
updated: 2026-09-20T09:00:00+02:00
---

# A
"""


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_load_item_returns_document_and_problems(tmp_path):
    path = write(tmp_path, "PROJECT.md", VALID.replace("status: active", "status: nope"))
    item = load_item(path, Kind.PROJECT)
    assert item.path == path
    assert item.kind is Kind.PROJECT
    assert item.doc.meta["name"] == "a"
    assert [p.field for p in item.problems] == ["status"]
    assert not item.valid


def test_valid_item(tmp_path):
    assert load_item(write(tmp_path, "PROJECT.md", VALID), Kind.PROJECT).valid


def test_load_items_skips_and_reports_broken_files(tmp_path):
    good = write(tmp_path, "good.md", VALID)
    broken = write(tmp_path, "broken.md", "no frontmatter")
    binary = tmp_path / "binary.md"
    binary.write_bytes(b"\xff\xfe")
    missing = tmp_path / "missing.md"
    items, failures = load_items([good, broken, binary, missing], Kind.PROJECT)
    assert [item.path for item in items] == [good]
    assert [failure.path for failure in failures] == [broken, binary, missing]
    assert all(failure.message for failure in failures)


def test_name_comes_from_the_path(ws):
    ws.project("p")
    for path, expected in [
        (ws.root / "p/PROJECT.md", "p"),
        (ws.task("p", "live"), "live"),
        (ws.task("p", "old", archived=True), "old"),
        (ws.decision("p", "d"), "d"),
    ]:
        kind = Kind.PROJECT if path.name == "PROJECT.md" else Kind.TASK
        assert load_item(path, kind).name == expected
