from datetime import date, datetime, timedelta, timezone

import pytest

from chreos.errors import FormatError
from chreos.frontmatter import Document, dump, load, parse, save
from chreos.model import Priority

TASK = """\
---
name: redesign-homepage   # cache
title: 'Fix: "quotes" # not a comment'
summary: New hero section.
project: website-relaunch
phase: open
status: in-progress
source:
  type: git
  path: website              # relative
priority: high
due: 2026-10-15
labels:
  - urgent
  - area=frontend
dependencies: []
custom_field: {keep: me}
created: 2026-09-21T10:00:00+02:00
updated: 2026-09-25T17:45:00+02:00
---

# Fix

Body with odd   spacing	and tabs.

---

```yaml
---
not: frontmatter
---
```
"""


def test_noop_round_trip_is_identical():
    assert dump(parse(TASK)) == TASK


def test_body_is_everything_after_the_closing_delimiter():
    doc = parse(TASK)
    assert doc.body.startswith("\n# Fix\n")
    assert doc.body.endswith("---\n```\n")


def test_values_are_parsed():
    meta = parse(TASK).meta
    assert meta["title"] == 'Fix: "quotes" # not a comment'
    assert meta["due"] == date(2026, 10, 15)
    assert meta["created"] == datetime(2026, 9, 21, 10, tzinfo=timezone(timedelta(hours=2)))
    assert meta["source"]["path"] == "website"
    assert meta["custom_field"] == {"keep": "me"}


def test_changing_one_key_changes_only_that_line():
    doc = parse(TASK)
    doc.meta["status"] = "done"
    expected = TASK.replace("status: in-progress", "status: done")
    assert dump(doc) == expected


def test_new_timestamp_is_written_unquoted_with_t_separator():
    doc = parse(TASK)
    doc.meta["updated"] = datetime(2026, 10, 2, 9, 5, 7, tzinfo=timezone(timedelta(hours=2)))
    assert "updated: 2026-10-02T09:05:07+02:00\n" in dump(doc)


def test_none_is_written_as_null():
    doc = parse(TASK)
    doc.meta["priority"] = None
    doc.meta["new_key"] = None
    out = dump(doc)
    assert "priority: null\n" in out
    assert "new_key: null\n" in out


def test_loaded_null_round_trips():
    text = "---\nsource: null\nsummary: null\n---\n"
    assert dump(parse(text)) == text


def test_enum_values_are_written_as_plain_strings():
    doc = parse(TASK)
    doc.meta["priority"] = Priority.LOW
    assert "priority: low\n" in dump(doc)


def test_strings_needing_quotes_stay_valid():
    doc = parse("---\ntitle: x\n---\n")
    doc.meta["title"] = "a: b # c"
    doc.meta["other"] = "2026-10-02"
    reparsed = parse(dump(doc))
    assert reparsed.meta["title"] == "a: b # c"
    assert reparsed.meta["other"] == "2026-10-02"


def test_new_lists_use_block_style_with_indent():
    doc = parse("---\nname: a\n---\n")
    doc.meta["labels"] = ["urgent", "area=frontend"]
    assert "labels:\n  - urgent\n  - area=frontend\n" in dump(doc)


def test_long_values_are_not_folded():
    doc = parse("---\nname: a\n---\n")
    summary = " ".join(["word"] * 60)
    doc.meta["summary"] = summary
    assert f"summary: {summary}\n" in dump(doc)


def test_crlf_round_trip():
    text = "---\r\nname: a\r\ntitle: A\r\n---\r\n\r\n# A\r\n"
    doc = parse(text)
    assert doc.meta["title"] == "A"
    assert doc.body == "\r\n# A\r\n"
    assert dump(doc) == text


def test_empty_body_and_missing_trailing_newline():
    assert parse("---\nname: a\n---\n").body == ""
    assert parse("---\nname: a\n---").body == ""


@pytest.mark.parametrize(
    "text",
    [
        "",
        "# no frontmatter\n",
        "\n---\nname: a\n---\n",
        "---\nname: a\n",
        "---\nname: [unclosed\n---\n",
        "---\n- a list\n---\n",
        "---\n---\n",
        "---\njust a string\n---\n",
    ],
)
def test_unparseable_frontmatter_raises_format_error(text):
    with pytest.raises(FormatError):
        parse(text)


def test_load_and_save(tmp_path):
    path = tmp_path / "TASK.md"
    path.write_text(TASK, encoding="utf-8")
    doc = load(path)
    doc.meta["status"] = "done"
    save(path, doc)
    assert path.read_text(encoding="utf-8") == TASK.replace("in-progress", "done")


def test_load_reports_the_path(tmp_path):
    path = tmp_path / "TASK.md"
    path.write_text("nothing here")
    with pytest.raises(FormatError, match=str(path)):
        load(path)


def test_document_from_scratch():
    doc = Document.new({"name": "a", "labels": []}, "\n# A\n")
    assert dump(doc) == "---\nname: a\nlabels: []\n---\n\n# A\n"


def test_shared_values_are_not_written_as_aliases():
    stamp = datetime(2026, 10, 2, 9, tzinfo=timezone.utc)
    labels = ["a"]
    doc = Document.new({"created": stamp, "updated": stamp, "x": labels, "y": labels}, "")
    out = dump(doc)
    assert "&" not in out and "*" not in out
