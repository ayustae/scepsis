from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from idion.files import LoadedFile
from idion.frontmatter import parse
from idion.identifiers import parse_file_id, parse_identifier
from idion.listing import Entry
from idion.output import check_report, jsonable, list_entry, list_line, show_entry, sorted_findings, table
from idion.tree import Finding


def test_jsonable_converts_yaml_values():
    meta = parse(
        "---\ndescription: x\nsince: 2026-10-15\nat: 2026-10-02T09:00:00+02:00\n"
        "nested: {a: [1, {b: null}]}\n---\n"
    ).meta
    assert jsonable(meta) == {
        "description": "x",
        "since": "2026-10-15",
        "at": "2026-10-02T09:00:00+02:00",
        "nested": {"a": [1, {"b": None}]},
    }


def test_jsonable_plain_values():
    assert jsonable(date(2026, 1, 2)) == "2026-01-02"
    assert jsonable(datetime(2026, 1, 2, 3, tzinfo=timezone(timedelta(hours=1)))) == "2026-01-02T03:00:00+01:00"
    assert jsonable({1: "a"}) == {"1": "a"}


def test_show_entry_for_a_valid_file(tmp_path):
    text = "---\ndescription: The user.\n---\n\n# User\n"
    loaded = LoadedFile(parse_file_id("user"), tmp_path / "user.md", text, parse(text), [])
    assert show_entry(loaded) == {
        "id": "user",
        "path": str(tmp_path / "user.md"),
        "frontmatter": {"description": "The user."},
        "body": "\n# User\n",
        "problems": [],
    }


def test_show_entry_for_a_broken_file(tmp_path):
    loaded = LoadedFile(parse_file_id("user"), tmp_path / "user.md", "text\n", None, ["no frontmatter"])
    entry = show_entry(loaded)
    assert entry["frontmatter"] is None
    assert entry["body"] == "text\n"
    assert entry["problems"] == ["no frontmatter"]


def entry(id_text, kind, description, files=None, path="/c/x"):
    return Entry(parse_identifier(id_text), kind, description, Path(path), files)


@pytest.mark.parametrize(
    ("value", "line"),
    [
        (entry("user", "file", "The user."), "user — The user."),
        (entry("broken", "file", None), "broken — (invalid description)"),
        (entry("teams/", "folder", "Teams.", 2), "teams/ — Teams. (2 files)"),
        (entry("teams/", "folder", "Teams.", 1), "teams/ — Teams. (1 file)"),
        (entry("notes/", "folder", None, 3), "notes/ — (no description) (3 files)"),
        (entry("teams/", "folder", "Teams."), "teams/ — Teams."),
    ],
)
def test_list_line(value, line):
    assert list_line(value) == line


def test_list_entry():
    assert list_entry(entry("user", "file", "The user.", path="/c/user.md")) == {
        "id": "user", "kind": "file", "description": "The user.", "path": "/c/user.md",
    }
    assert list_entry(entry("notes/", "folder", None, 3, "/c/notes")) == {
        "id": "notes/", "kind": "folder", "description": None, "path": "/c/notes", "files": 3,
    }


def test_table_aligns_columns():
    assert table([("web", "active", "Website"), ("a", "inactive", "A")]) == [
        "web  active    Website",
        "a    inactive  A",
    ]
    assert table([]) == []


def test_sorted_findings_puts_errors_first_then_paths():
    findings = [
        Finding("warning", Path("/c/a"), None, "w"),
        Finding("error", Path("/c/z"), None, "e2"),
        Finding("error", Path("/c/b"), "b", "e1"),
    ]
    assert [f.message for f in sorted_findings(findings)] == ["e1", "e2", "w"]


def test_check_report():
    findings = [Finding("warning", Path("/c/a"), "a/", "w"), Finding("error", Path("/c/b.md"), "b", "e")]
    assert check_report(findings) == {
        "findings": [
            {"severity": "error", "path": "/c/b.md", "id": "b", "message": "e"},
            {"severity": "warning", "path": "/c/a", "id": "a/", "message": "w"},
        ],
        "errors": 1,
        "warnings": 1,
    }
