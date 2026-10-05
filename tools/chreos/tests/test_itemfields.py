import pytest

from chreos.errors import ChreosError
from chreos.frontmatter import parse
from chreos.itemfields import split_labels, update_common
from chreos.model import ProjectStatus

DOC = """\
---
name: web
title: Web
summary: Old summary.
status: active
labels:
  - client=acme
---

# Web

Old summary.
"""


def update(text=DOC, **kwargs):
    doc = parse(text)
    defaults = dict(title=None, summary=None, add_labels=(), remove_labels=(), status=None, statuses=ProjectStatus)
    changed, warnings = update_common(doc, **{**defaults, **kwargs})
    return doc, changed, warnings


def test_split_labels():
    assert split_labels(["a,B=c", "d", "a"]) == ["a", "b=c", "d"]
    assert split_labels([]) == []
    with pytest.raises(ChreosError, match="invalid label"):
        split_labels(["a,,b"])


def test_nothing_changes():
    doc, changed, warnings = update()
    assert not changed and warnings == []


def test_title_and_summary_sync_body():
    doc, changed, warnings = update(title="Website", summary="New.")
    assert changed and warnings == []
    assert (doc.meta["title"], doc.meta["summary"]) == ("Website", "New.")
    assert doc.body == "\n# Website\n\nNew.\n"


def test_summary_none_clears_and_removes_paragraph():
    doc, changed, _ = update(summary="none")
    assert changed and doc.meta["summary"] is None
    assert doc.body == "\n# Web\n"


def test_diverged_body_warns():
    doc, changed, warnings = update(DOC.replace("# Web\n", "# Hand edited\n"), title="Website")
    assert changed and doc.meta["title"] == "Website"
    assert "H1" in warnings[0]


def test_same_value_is_not_a_change():
    _, changed, _ = update(title="Web", summary="Old summary.", status="active", add_labels=["client=acme"])
    assert not changed


def test_labels_added_and_removed():
    doc, changed, _ = update(add_labels=["Urgent", "client=acme"], remove_labels=["client=acme", "missing"])
    assert changed and list(doc.meta["labels"]) == ["urgent"]


def test_labels_created_when_absent():
    doc, _, _ = update(DOC.replace("labels:\n  - client=acme\n", ""), add_labels=["x"])
    assert list(doc.meta["labels"]) == ["x"]


@pytest.mark.parametrize(("kwargs", "match"), [({"status": "pending"}, "invalid status"), ({"title": " "}, "title"), ({"add_labels": ["a b"]}, "invalid label")])
def test_invalid_values(kwargs, match):
    with pytest.raises(ChreosError, match=match):
        update(**kwargs)


def test_multiline_title_refused():
    with pytest.raises(ChreosError, match="title"):
        update(title="a\nb")
