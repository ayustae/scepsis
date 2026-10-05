import json
from datetime import date, datetime, timedelta, timezone

from chreos.frontmatter import parse
from chreos.items import LoadedItem
from chreos.model import Kind, Priority
from chreos.output import jsonable, list_entry, show_entry, table

DOC = "---\nname: t\ntitle: T\nstatus: todo\ndue: 2026-10-15\ncreated: 2026-09-21T10:00:00+02:00\nlabels: [a]\nsource: {type: git, path: x}\n---\n\n# T\n"


def test_jsonable():
    value = {
        "when": datetime(2026, 9, 21, 10, tzinfo=timezone(timedelta(hours=2))),
        "day": date(2026, 10, 15),
        "prio": Priority.HIGH,
        "nested": [{"x": None}],
    }
    assert jsonable(value) == {
        "when": "2026-09-21T10:00:00+02:00",
        "day": "2026-10-15",
        "prio": "high",
        "nested": [{"x": None}],
    }


def test_entries_are_json_serializable_and_stable():
    from pathlib import Path

    loaded = LoadedItem(Path("/w/p/tasks/t/TASK.md"), Kind.TASK, parse(DOC), [])
    entry = list_entry(loaded)
    assert entry["due"] == "2026-10-15"
    assert entry["created"] == "2026-09-21T10:00:00+02:00"
    assert entry["source"] == {"type": "git", "path": "x"}
    assert entry["path"] == "/w/p/tasks/t/TASK.md"
    shown = show_entry(loaded)
    assert set(shown) == {"frontmatter", "body", "path"}
    assert shown["body"] == "\n# T\n"
    json.dumps([entry, shown])


def test_table_aligns_columns():
    assert table([("web", "active", "Website"), ("a", "inactive", "A")]) == [
        "web  active    Website",
        "a    inactive  A",
    ]
    assert table([]) == []
