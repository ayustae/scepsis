import pytest

from chreos.dependencies import apply_dependency_changes, dependency_checks
from chreos.errors import ChreosError
from chreos.frontmatter import load
from chreos.graph import Graph, Node
from chreos.model import Kind


def test_apply_changes(ws):
    ws.project("p")
    ws.task("p", "a")
    ws.decision("p", "d")
    path = ws.task("p", "t", dependencies=["task:a", "task:p/x"])
    meta = load(path).meta
    graph = Graph.load(ws.workspace)
    warnings = apply_dependency_changes(meta, graph, Node(Kind.TASK, "p", "t"), add=["decision:d", "task:p/a"], remove=["task:p/x", "task:nope"])
    assert list(meta["dependencies"]) == ["task:a", "decision:d"]
    assert len(warnings) == 1 and "task:nope" in warnings[0]


def test_apply_creates_a_missing_list(ws):
    ws.project("p")
    meta = {}
    assert apply_dependency_changes(meta, Graph.load(ws.workspace), Node(Kind.TASK, "p", "t"), add=[], remove=[]) == []
    assert meta == {"dependencies": []}


def test_apply_refuses_cycles(ws):
    ws.project("p")
    ws.task("p", "t")
    ws.decision("p", "d", dependencies=["task:t"])
    with pytest.raises(ChreosError, match="cycle"):
        apply_dependency_changes({}, Graph.load(ws.workspace), Node(Kind.TASK, "p", "t"), add=["decision:d"], remove=[])


def test_dependency_checks(ws):
    ws.project("p")
    ws.decision("p", "a", dependencies=["decision:b", "task:gone"])
    ws.decision("p", "b", dependencies=["decision:a"])
    errors = dependency_checks(ws.workspace, Node(Kind.DECISION, "p", "a"))
    assert any("task:gone" in e for e in errors)
    assert any("cycle" in e and "decision:p/b" in e for e in errors)
