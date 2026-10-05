from datetime import date

import pytest

from chreos.errors import ChreosError
from chreos.frontmatter import load
from chreos.graph import Graph, Node
from chreos.items import load_item
from chreos.model import Kind, SourceType
from chreos.tasks import create_task, resolve_task, set_assignee, task_checks, task_predicate, update_task

BASES = {SourceType.GIT: None, SourceType.LOCAL: None}
YES = lambda _: True  # noqa: E731


def create(ws, project, name, **kwargs):
    return create_task(ws.workspace, Graph.load(ws.workspace), project, name, bases=BASES, **kwargs)


def update(ws, project, name, confirm=YES, **kwargs):
    return update_task(ws.workspace, Graph.load(ws.workspace), project, name, confirm=confirm, bases=BASES, **kwargs)


@pytest.fixture
def p(ws):
    ws.project("p")
    ws.project("q")
    return ws


class TestResolve:
    def test_forms(self, p):
        w = p.workspace
        assert resolve_task(w, "t", None, "default") == ("default", "t")
        assert resolve_task(w, "t", "p", "default") == ("p", "t")
        assert resolve_task(w, "q/t", None, "default") == ("q", "t")
        assert resolve_task(w, "q/t", "q", "default") == ("q", "t")
        with pytest.raises(ChreosError, match="conflicts"):
            resolve_task(w, "q/t", "p", "default")


class TestCreate:
    def test_all_fields(self, p, tmp_path):
        p.task("q", "dep")
        path, warnings = create(
            p, "p", "t", title="T", summary="S", labels=["a,b"], source_type="local", source_path=str(tmp_path),
            priority="high", due="2026-10-15", assignee=" claude ", dependencies=["task:q/dep"],
        )
        assert path == p.root / "p/tasks/t/TASK.md" and warnings == []
        meta = load(path).meta
        assert (meta["phase"], meta["status"], meta["priority"], meta["due"], meta["assignee"]) == ("closed", "new", "high", date(2026, 10, 15), "claude")
        assert dict(meta["source"]) == {"type": "local", "path": str(tmp_path)}
        assert list(meta["labels"]) == ["a", "b"] and list(meta["dependencies"]) == ["task:q/dep"]

    def test_unresolvable_source_is_a_warning(self, p):
        _, warnings = create(p, "p", "t", source_type="git", source_path="relative")
        assert "source.git_path" in warnings[0]

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"source_type": "git"}, "together"),
            ({"source_path": "/x"}, "together"),
            ({"source_type": "svn", "source_path": "/x"}, "source type"),
            ({"priority": "urgent"}, "priority"),
            ({"due": "tomorrow"}, "due date"),
            ({"assignee": "a\nb"}, "assignee"),
            ({"dependencies": ["task:missing"]}, "does not resolve"),
            ({"dependencies": ["missing"]}, "did you mean"),
            ({"labels": ["a b"]}, "invalid label"),
        ],
    )
    def test_invalid_input_creates_nothing(self, p, kwargs, match):
        with pytest.raises(ChreosError, match=match):
            create(p, "p", "t", **kwargs)
        assert not (p.root / "p/tasks/t").exists()

    def test_name_and_project_checks(self, p):
        p.task("p", "old", archived=True)
        with pytest.raises(ChreosError, match="already exists"):
            create(p, "p", "old")
        with pytest.raises(ChreosError, match="project 'nope' does not exist"):
            create(p, "nope", "t")
        with pytest.raises(ChreosError, match="invalid name"):
            create(p, "p", "Bad")


class TestUpdate:
    def test_fields_and_updated_bump(self, p):
        path = p.task("p", "t", priority="low", due=date(2026, 1, 1), assignee="me")
        before = load(path).meta["updated"]
        warnings = update(p, "p", "t", title="New", priority="none", due="2026-12-24", assignee="none", status="cancelled")
        meta = load(path).meta
        assert (meta["title"], meta["priority"], meta["due"], meta["assignee"], meta["status"]) == ("New", None, date(2026, 12, 24), None, "cancelled")
        assert meta["updated"] >= before and warnings == []

    def test_status_must_fit_the_phase(self, p):
        path = p.task("p", "t")
        before = path.read_text()
        with pytest.raises(ChreosError, match="not allowed in phase 'closed'.*task open"):
            update(p, "p", "t", status="todo")
        assert path.read_text() == before

    def test_done_confirmation_uses_final_dependencies(self, p, no, yes):
        p.task("p", "blocker")
        path = p.task("p", "t", phase="open", status="in-progress", dependencies=["task:blocker"])
        with pytest.raises(ChreosError, match="cancelled"):
            update(p, "p", "t", status="done", confirm=no)
        assert "task:blocker (new)" in no.messages[0]
        update(p, "p", "t", status="done", remove_deps=["task:p/blocker"], confirm=yes)
        assert yes.messages == []
        meta = load(path).meta
        assert meta["status"] == "done" and list(meta["dependencies"]) == []

    def test_dependencies_add_remove_and_cycles(self, p):
        p.task("p", "a")
        p.task("p", "b", dependencies=["task:a"])
        path = p.task("p", "c")
        warnings = update(p, "p", "c", add_deps=["task:b", "task:a"], remove_deps=["task:zzz"])
        assert list(load(path).meta["dependencies"]) == ["task:b", "task:a"]
        assert "task:zzz" in warnings[0]
        with pytest.raises(ChreosError, match="cycle"):
            update(p, "p", "a", add_deps=["task:c"])
        update(p, "p", "c", add_deps=["task:b"])  # already present: no duplicate
        assert list(load(path).meta["dependencies"]) == ["task:b", "task:a"]

    def test_reassignment_needs_confirmation(self, p, no):
        path = p.task("p", "t", assignee="alice")
        with pytest.raises(ChreosError, match="cancelled"):
            update(p, "p", "t", assignee="bob", confirm=no)
        assert "alice" in no.messages[0] and "bob" in no.messages[0]
        assert load(path).meta["assignee"] == "alice"
        update(p, "p", "t", assignee="alice", confirm=no)  # same: no question
        update(p, "p", "t", assignee="none", confirm=no)  # clearing: no question
        assert load(path).meta["assignee"] is None

    def test_source_rules(self, p, tmp_path, ws):
        path = p.task("p", "t")
        with pytest.raises(ChreosError, match="together"):
            update(p, "p", "t", source_path="/x")
        update(p, "p", "t", source_type="local", source_path=str(tmp_path))
        update(p, "p", "t", source_type="git")
        assert dict(load(path).meta["source"]) == {"type": "git", "path": str(tmp_path)}
        text = path.read_text().replace("phase: closed", "phase: open").replace("status: new", "status: todo")
        path.write_text(text)
        with pytest.raises(ChreosError, match="close it first"):
            update(p, "p", "t", source_path="/y")

    def test_archived_and_missing(self, p):
        p.task("p", "old", archived=True)
        with pytest.raises(ChreosError, match="archived; restore it first"):
            update(p, "p", "old", title="x")
        with pytest.raises(ChreosError, match="does not exist"):
            update(p, "p", "nope", title="x")

    def test_noop_does_not_write(self, p):
        path = p.task("p", "t", priority="high")
        before = path.read_text()
        update(p, "p", "t", priority="high")
        assert path.read_text() == before


def test_set_assignee():
    meta = {"assignee": None}
    assert set_assignee(meta, "a", lambda _: False) and meta["assignee"] == "a"
    assert not set_assignee(meta, "a", lambda _: False)


class TestChecksAndPredicates:
    def test_task_checks(self, p):
        p.task("p", "a")
        path = p.task("p", "t", dependencies=["task:a", "task:gone"])
        path.write_text(path.read_text().replace("## References\n", "## References\n\n- decision:nope\n- https://ok.example\n"))
        errors, warnings = task_checks(p.workspace, "p", "t")(load(path))
        assert any("task:gone" in e for e in errors) and any("decision:nope" in e for e in errors)
        assert len(errors) == 2

    def test_predicates(self, p):
        p.task("p", "blocker")
        p.task("p", "a", priority="high", due=date(2020, 1, 1), assignee="me", phase="open", status="todo")
        p.task("p", "b", dependencies=["task:blocker"], due=date(2999, 1, 1))
        p.task("p", "c", status="done", due=date(2020, 1, 1))
        graph = Graph.load(p.workspace)
        items = [load_item(p.workspace.live_task_file("p", n), Kind.TASK) for n in ("a", "b", "blocker", "c")]

        def select(**kwargs):
            pred = task_predicate(graph, today=date(2026, 10, 2), **kwargs)
            return [i.name for i in items if pred(i)]

        assert select(phases={"open"}) == ["a"]
        assert select(priorities={"high"}) == ["a"]
        assert select(assignees={"me"}) == ["a"]
        assert select(unassigned=True) == ["b", "blocker", "c"]
        assert select(due_before=date(2026, 1, 1)) == ["a", "c"]
        assert select(overdue=True) == ["a"]
        assert select(ready=True) == ["a", "blocker"]
        assert select(depends_on=Node(Kind.TASK, "p", "blocker")) == ["b"]
