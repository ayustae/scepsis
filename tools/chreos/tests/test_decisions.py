import pytest

from chreos.decisions import create_decision, update_decision
from chreos.errors import ChreosError
from chreos.frontmatter import load
from chreos.graph import Graph

YES = lambda _: True  # noqa: E731


def create(ws, project, name, confirm=YES, **kwargs):
    return create_decision(ws.workspace, Graph.load(ws.workspace), project, name, confirm=confirm, **kwargs)


def update(ws, project, name, confirm=YES, **kwargs):
    return update_decision(ws.workspace, Graph.load(ws.workspace), project, name, confirm=confirm, **kwargs)


@pytest.fixture
def p(ws):
    ws.project("p")
    return ws


class TestCreate:
    def test_fields(self, p):
        p.task("p", "research", status="done")
        path = create(p, "p", "hosting", title="Hosting", summary="Where to host.", labels=["area=infra"],
                      dependencies=["task:research"], status="decided")
        assert path == p.root / "p/decisions/hosting.md"
        meta = load(path).meta
        assert (meta["title"], meta["status"], meta["project"]) == ("Hosting", "decided", "p")
        assert list(meta["dependencies"]) == ["task:research"] and list(meta["labels"]) == ["area=infra"]
        assert load(path).body == "\n# Hosting\n\nWhere to host.\n\n"

    def test_defaults(self, p):
        meta = load(create(p, "p", "d")).meta
        assert (meta["status"], meta["title"], list(meta["dependencies"])) == ("pending", "d", [])

    def test_decided_with_unsatisfied_dependencies_asks(self, p, no):
        p.task("p", "research")
        with pytest.raises(ChreosError, match="cancelled"):
            create(p, "p", "d", dependencies=["task:research"], status="decided", confirm=no)
        assert "task:research (new)" in no.messages[0]
        assert not (p.root / "p/decisions/d.md").exists()

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [({"status": "done"}, "invalid status"), ({"dependencies": ["task:nope"]}, "does not resolve"), ({"labels": ["a b"]}, "label")],
    )
    def test_invalid(self, p, kwargs, match):
        with pytest.raises(ChreosError, match=match):
            create(p, "p", "d", **kwargs)
        assert not (p.root / "p/decisions/d.md").exists()

    def test_name_and_project(self, p):
        p.decision("p", "taken")
        p.task("p", "shared-name")
        with pytest.raises(ChreosError, match="already exists"):
            create(p, "p", "taken")
        create(p, "p", "shared-name")  # tasks and decisions are separate namespaces
        with pytest.raises(ChreosError, match="does not exist"):
            create(p, "nope", "d")


class TestUpdate:
    def test_fields_and_dependencies(self, p):
        p.task("p", "a")
        p.decision("p", "other")
        path = p.decision("p", "d", dependencies=["task:a"])
        before = load(path).meta["updated"]
        warnings = update(p, "p", "d", title="D", add_deps=["decision:other"], remove_deps=["task:p/a", "task:x"])
        meta = load(path).meta
        assert meta["title"] == "D" and list(meta["dependencies"]) == ["decision:other"]
        assert meta["updated"] >= before and "task:x" in warnings[0]

    def test_decided_confirmation_uses_final_dependencies(self, p, no, yes):
        p.task("p", "open-question")
        path = p.decision("p", "d", dependencies=["task:open-question"])
        with pytest.raises(ChreosError, match="cancelled"):
            update(p, "p", "d", status="decided", confirm=no)
        assert load(path).meta["status"] == "pending"
        update(p, "p", "d", status="decided", remove_deps=["task:open-question"], confirm=yes)
        assert yes.messages == [] and load(path).meta["status"] == "decided"

    def test_cycle_refused(self, p):
        p.decision("p", "a", dependencies=["decision:b"])
        p.decision("p", "b")
        with pytest.raises(ChreosError, match="cycle"):
            update(p, "p", "b", add_deps=["decision:a"])

    def test_noop_and_missing(self, p):
        path = p.decision("p", "d")
        before = path.read_text()
        update(p, "p", "d", status="pending")
        assert path.read_text() == before
        with pytest.raises(ChreosError, match="does not exist"):
            update(p, "p", "nope", title="x")
