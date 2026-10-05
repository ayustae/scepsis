import pytest

from chreos.frontmatter import parse
from chreos.model import Kind
from chreos.schema import Problem, validate

PROJECT = """\
---
name: website-relaunch
title: Website Relaunch
summary: Rebuild the site.
status: active
labels:
  - client=acme
created: 2026-09-20T09:00:00+02:00
updated: 2026-09-25T17:40:00+02:00
---
"""

TASK = """\
---
name: redesign-homepage
title: Redesign homepage
summary: null
project: website-relaunch
phase: open
status: in-progress
source:
  type: git
  path: website
priority: high
due: 2026-10-15
assignee: claude
labels: []
dependencies:
  - task:migrate-cms
created: 2026-09-21T10:00:00+02:00
updated: 2026-09-25T17:45:00+02:00
---
"""

DECISION = """\
---
name: hosting-provider
title: Hosting provider
summary: Where the site will be hosted.
project: website-relaunch
status: decided
labels: []
dependencies: []
created: 2026-09-22T11:00:00+02:00
updated: 2026-09-26T09:30:00+02:00
---
"""

SAMPLES = {Kind.PROJECT: PROJECT, Kind.TASK: TASK, Kind.DECISION: DECISION}


def problems(kind, text=None, **changes):
    meta = parse(text or SAMPLES[kind]).meta
    for key, value in changes.items():
        if value is ...:
            del meta[key]
        else:
            meta[key] = value
    return validate(kind, meta)


def fields(found):
    return {problem.field for problem in found}


@pytest.mark.parametrize("kind", list(Kind))
def test_valid_samples_have_no_problems(kind):
    assert problems(kind) == []


@pytest.mark.parametrize("kind", list(Kind))
def test_unknown_keys_are_allowed(kind):
    assert problems(kind, extra={"anything": 1}) == []


@pytest.mark.parametrize("kind", list(Kind))
@pytest.mark.parametrize("field", ["name", "title", "status", "created", "updated"])
def test_missing_common_required_fields(kind, field):
    assert problems(kind, **{field: ...}) == [Problem(field, "missing required field")]


@pytest.mark.parametrize("kind", list(Kind))
def test_optional_common_fields_may_be_absent(kind):
    assert problems(kind, summary=..., labels=...) == []


@pytest.mark.parametrize(
    ("kind", "status"),
    [(Kind.PROJECT, "pending"), (Kind.DECISION, "active"), (Kind.TASK, "decided")],
)
def test_status_must_belong_to_the_item_type(kind, status):
    assert fields(problems(kind, status=status)) == {"status"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "Bad_Name"),
        ("name", 3),
        ("title", ""),
        ("title", ["x"]),
        ("summary", 5),
        ("labels", "urgent"),
        ("labels", ["Bad label"]),
        ("labels", ["UPPER"]),
        ("created", "yesterday"),
        ("created", "2026-09-21T10:00:00"),
        ("updated", None),
    ],
)
def test_invalid_common_values(field, value):
    assert fields(problems(Kind.PROJECT, **{field: value})) == {field}


def test_quoted_timestamp_with_offset_is_accepted():
    assert problems(Kind.PROJECT, created="2026-09-21T10:00:00+02:00") == []


def test_uppercase_labels_are_reported_as_not_normalized():
    found = problems(Kind.PROJECT, labels=["Urgent"])
    assert "lowercase" in found[0].message


@pytest.mark.parametrize("field", ["project", "phase"])
def test_task_required_fields(field):
    assert problems(Kind.TASK, **{field: ...}) == [Problem(field, "missing required field")]


@pytest.mark.parametrize(
    "field", ["source", "priority", "due", "assignee", "dependencies", "summary", "labels"]
)
def test_task_optional_fields_may_be_absent(field):
    assert problems(Kind.TASK, **{field: ...}) == []


@pytest.mark.parametrize(
    "field", ["source", "priority", "due", "assignee", "summary"]
)
def test_task_optional_scalars_may_be_null(field):
    assert problems(Kind.TASK, **{field: None}) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project", "Not Valid"),
        ("phase", "half-open"),
        ("priority", "urgent"),
        ("due", "2026-10-15"),
        ("due", "soon"),
        ("assignee", "a\nb"),
        ("assignee", ""),
        ("dependencies", "task:a"),
        ("dependencies", [1]),
        ("source", "website"),
        ("source", {"type": "svn", "path": "x"}),
        ("source", {"type": "git"}),
        ("source", {"type": "git", "path": ""}),
        ("source", {"type": "git", "path": "x", "extra": 1}),
        ("archived", "never"),
    ],
)
def test_invalid_task_values(field, value):
    assert fields(problems(Kind.TASK, **{field: value})) == {field}


def test_due_as_datetime_is_invalid():
    text = TASK.replace("due: 2026-10-15", "due: 2026-10-15T10:00:00+02:00")
    assert fields(problems(Kind.TASK, text)) == {"due"}


def test_archived_timestamp_is_valid():
    assert problems(Kind.TASK, phase="closed", status="done", archived="2026-09-30T10:00:00+02:00") == []


def test_status_not_allowed_in_phase():
    found = problems(Kind.TASK, phase="closed", status="in-progress")
    assert fields(found) == {"status"}
    assert "phase 'closed'" in found[0].message


def test_phase_status_check_skipped_when_phase_is_invalid():
    assert fields(problems(Kind.TASK, phase="weird")) == {"phase"}


@pytest.mark.parametrize(("field", "value"), [("project", ...), ("dependencies", "x")])
def test_decision_fields(field, value):
    assert fields(problems(Kind.DECISION, **{field: value})) == {field}


def test_problem_str():
    assert str(Problem("status", "bad")) == "status: bad"
