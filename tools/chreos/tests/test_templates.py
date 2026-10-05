from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from chreos.errors import ChreosError
from chreos.frontmatter import dump, parse
from chreos.model import Kind
from chreos.schema import validate
from chreos.templates import TEMPLATE_FILES, packaged_template, render

REPO_TEMPLATES = Path(__file__).resolve().parents[3] / "templates"
WHEN = datetime(2026, 10, 2, 9, 0, tzinfo=timezone(timedelta(hours=2)))


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.mark.skipif(not REPO_TEMPLATES.is_dir(), reason="repository templates/ not available")
@pytest.mark.parametrize("kind", list(Kind))
def test_packaged_templates_match_repository(kind):
    repo = (REPO_TEMPLATES / TEMPLATE_FILES[kind]).read_text(encoding="utf-8")
    assert packaged_template(kind) == repo


@pytest.mark.parametrize("kind", list(Kind))
def test_rendered_items_are_valid(kind):
    doc = render(kind, name="my-item", project="default", summary="One line.", timestamp=WHEN)
    assert validate(kind, doc.meta) == []


def test_render_task():
    doc = render(
        Kind.TASK,
        name="redesign-homepage",
        title="Redesign homepage",
        summary="New hero section.",
        project="website",
        timestamp=WHEN,
        fields={"priority": "high", "due": date(2026, 10, 15), "labels": ["urgent"]},
    )
    assert dump(doc) == """\
---
name: redesign-homepage
title: Redesign homepage
summary: New hero section.
project: website
phase: closed
status: new
source: null
priority: high
due: 2026-10-15
assignee: null
labels:
  - urgent
dependencies: []
created: 2026-10-02T09:00:00+02:00
updated: 2026-10-02T09:00:00+02:00
---

# Redesign homepage

New hero section.

## Description

## Acceptance criteria

## References

## Notes

"""


def test_title_defaults_to_name():
    doc = render(Kind.PROJECT, name="my-project", timestamp=WHEN)
    assert doc.meta["title"] == "my-project"
    assert doc.body.startswith("\n# my-project\n")


@pytest.mark.parametrize("kind", list(Kind))
def test_no_summary_means_null_and_no_paragraph(kind):
    doc = render(kind, name="a", project="p", timestamp=WHEN)
    assert doc.meta["summary"] is None
    assert "<summary>" not in doc.body
    assert "\n\n\n" not in doc.body
    assert doc.body.startswith("\n# a\n")


def test_decision_without_summary():
    doc = render(Kind.DECISION, name="a", project="p", timestamp=WHEN)
    assert doc.body == "\n# a\n\n## Description\n\n"


def test_decision_has_a_description_section():
    doc = render(Kind.DECISION, name="a", project="p", summary="Why.", timestamp=WHEN)
    assert doc.body == "\n# a\n\nWhy.\n\n## Description\n\n"


def test_special_characters_stay_valid_yaml():
    title = 'Fix: "quotes" # not a comment'
    doc = render(Kind.PROJECT, name="a", title=title, summary="- a: b", timestamp=WHEN)
    reparsed = parse(dump(doc))
    assert reparsed.meta["title"] == title
    assert reparsed.meta["summary"] == "- a: b"
    assert f"# {title}\n" in reparsed.body


def test_timestamp_defaults_to_now():
    doc = render(Kind.PROJECT, name="a")
    assert doc.meta["created"] == doc.meta["updated"]
    assert doc.meta["created"].tzinfo is not None


def test_unknown_field_is_refused():
    with pytest.raises(ChreosError, match="not in the project template"):
        render(Kind.PROJECT, name="a", fields={"bogus": 1}, timestamp=WHEN)


def test_task_requires_project():
    with pytest.raises(ChreosError, match="project"):
        render(Kind.TASK, name="a", timestamp=WHEN)


def write_override(home, kind, text):
    folder = home / ".scepsis" / "templates"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / TEMPLATE_FILES[kind]).write_text(text, encoding="utf-8")


def test_override_is_used(home):
    text = packaged_template(Kind.PROJECT).replace("## Description", "## Goals")
    text = text.replace("labels: []", "labels: []\nowner: null  # extra key")
    write_override(home, Kind.PROJECT, text)
    doc = render(Kind.PROJECT, name="a", timestamp=WHEN)
    assert "## Goals" in doc.body
    assert "owner: null  # extra key" in dump(doc)


def test_override_missing_a_key_is_refused(home):
    text = packaged_template(Kind.PROJECT).replace("labels: []\n", "")
    write_override(home, Kind.PROJECT, text)
    with pytest.raises(ChreosError, match="labels"):
        render(Kind.PROJECT, name="a", timestamp=WHEN)


def test_unparseable_override_is_refused(home):
    write_override(home, Kind.PROJECT, "no frontmatter")
    with pytest.raises(ChreosError, match="PROJECT.md"):
        render(Kind.PROJECT, name="a", timestamp=WHEN)


def test_unknown_placeholder_is_refused(home):
    text = packaged_template(Kind.PROJECT).replace("labels: []", "labels: []\nowner: <owner>")
    write_override(home, Kind.PROJECT, text)
    with pytest.raises(ChreosError, match="<owner>"):
        render(Kind.PROJECT, name="a", timestamp=WHEN)
