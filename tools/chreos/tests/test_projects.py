import pytest

from chreos.errors import ChreosError
from chreos.frontmatter import load
from chreos.model import Kind
from chreos.projects import create_project
from chreos.schema import validate


def test_creates_folders_and_project_file(ws):
    path = create_project(ws.workspace, "web", title="Web", summary="Site.", labels=["Client=Acme"])
    assert path == ws.root / "web" / "PROJECT.md"
    for folder in ("tasks", ".archive", "decisions"):
        assert (ws.root / "web" / folder).is_dir()
    meta = load(path).meta
    assert (meta["title"], meta["summary"], meta["labels"], meta["status"]) == ("Web", "Site.", ["client=acme"], "active")
    assert validate(Kind.PROJECT, meta) == []
    assert ws.workspace.projects() == ["web"]


def test_defaults(ws):
    meta = load(create_project(ws.workspace, "web")).meta
    assert (meta["title"], meta["summary"], meta["labels"]) == ("web", None, [])


def test_inactive_status(ws):
    assert load(create_project(ws.workspace, "web", status="inactive")).meta["status"] == "inactive"


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"name": "Bad"}, "invalid name"),
        ({"name": "web", "status": "pending"}, "invalid project status"),
        ({"name": "web", "labels": ["a b"]}, "invalid label"),
    ],
)
def test_invalid_input(ws, kwargs, match):
    name = kwargs.pop("name")
    with pytest.raises(ChreosError, match=match):
        create_project(ws.workspace, name, **kwargs)
    assert ws.workspace.projects() == []


def test_existing_project(ws):
    create_project(ws.workspace, "web")
    with pytest.raises(ChreosError, match="already exists"):
        create_project(ws.workspace, "web")


def test_missing_workspace(tmp_path):
    from chreos.workspace import Workspace

    with pytest.raises(ChreosError, match="workspace .* does not exist"):
        create_project(Workspace(tmp_path / "nope"), "web")
