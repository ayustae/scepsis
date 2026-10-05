from datetime import datetime, timezone

import pytest

from chreos.frontmatter import parse
from chreos.items import LoadedItem
from chreos.listing import Filters, filter_items, sort_items
from chreos.model import Kind


def item(name, *, title=None, summary=None, status="active", labels=(), body="", created=None, updated=None):
    lines = [f"name: {name}", f"title: {title or name}", f"status: {status}", f"labels: {list(labels)}"]
    if summary:
        lines.append(f"summary: {summary}")
    for key, value in (("created", created), ("updated", updated)):
        if value:
            lines.append(f"{key}: {value}")
    doc = parse("---\n" + "\n".join(lines) + "\n---\n" + body)
    from pathlib import Path

    return LoadedItem(Path(f"/w/{name}/PROJECT.md"), Kind.PROJECT, doc, [])


ITEMS = [
    item("web", title="Website Relaunch", summary="Public site", labels=["client=acme", "urgent"], body="Uses Hugo"),
    item("api", title="API", status="inactive", labels=["client=globex"], body="REST"),
    item("docs", summary="Handbook", labels=["client"]),
]


def names(items):
    return [i.name for i in items]


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        (Filters(), ["web", "api", "docs"]),
        (Filters(name="E"), ["web"]),
        (Filters(title="relaunch"), ["web"]),
        (Filters(summary="hand"), ["docs"]),
        (Filters(search="hugo"), ["web"]),
        (Filters(labels=["client"]), ["web", "api", "docs"]),
        (Filters(labels=["client=acme"]), ["web"]),
        (Filters(labels=["Client=ACME", "urgent"]), ["web"]),
        (Filters(labels=["client=acme", "client=globex"]), []),
        (Filters(statuses={"inactive"}), ["api"]),
        (Filters(statuses={"active", "inactive"}, name="a"), ["api"]),
    ],
)
def test_filters(filters, expected):
    assert names(filter_items(ITEMS, filters)) == expected


def test_missing_summary_never_matches_summary_filter():
    assert names(filter_items([item("x")], Filters(summary="x"))) == []


def test_sort():
    early = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()
    late = datetime(2026, 6, 1, tzinfo=timezone.utc).isoformat()
    items = [
        item("b", status="inactive", created=late, updated=early),
        item("a", status="active", created=early),
        item("c", status="active", created=late, updated=late),
    ]
    assert names(sort_items(items, "name")) == ["a", "b", "c"]
    assert names(sort_items(items, "created")) == ["a", "b", "c"]
    assert names(sort_items(items, "updated")) == ["b", "c", "a"]  # missing last
    assert names(sort_items(items, "status")) == ["a", "c", "b"]


def task_item(name, priority=None, due=None):
    lines = [f"name: {name}", "title: x", "status: new"]
    if priority:
        lines.append(f"priority: {priority}")
    if due:
        lines.append(f"due: {due}")
    from pathlib import Path

    return LoadedItem(Path(f"/w/p/tasks/{name}/TASK.md"), Kind.TASK, parse("---\n" + "\n".join(lines) + "\n---\n"), [])


def test_sort_by_priority_and_due():
    items = [
        task_item("a", priority="low", due="2026-12-01"),
        task_item("b"),
        task_item("c", priority="critical", due="2026-10-01"),
        task_item("d", priority="medium"),
    ]
    assert names(sort_items(items, "priority")) == ["c", "d", "a", "b"]
    assert names(sort_items(items, "due")) == ["c", "a", "b", "d"]


def test_extra_predicate():
    assert names(filter_items(ITEMS, Filters(), extra=lambda i: i.name != "web")) == ["api", "docs"]
