import pytest

from chreos.errors import ChreosError
from chreos.graph import DependencyStatus, Graph, Node
from chreos.model import Kind


def task(project, name):
    return Node(Kind.TASK, project, name)


def decision(project, name):
    return Node(Kind.DECISION, project, name)


@pytest.fixture
def sample(ws):
    """
    web: design (decided) <- homepage (todo, open) -> cms (done)
         homepage -> tooling/build-cli (in-progress, open)
         copy (new) -> homepage
         old (archived, done)
         launch (pending) -> task:copy
    tooling: build-cli (in-progress, open), docs (new) -> decision:web/launch
    """
    ws.project("web")
    ws.project("tooling")
    ws.decision("web", "design", status="decided")
    ws.task("web", "cms", status="done")
    ws.task("tooling", "build-cli", phase="open", status="in-progress")
    ws.task(
        "web",
        "homepage",
        phase="open",
        status="todo",
        dependencies=["decision:design", "task:cms", "task:tooling/build-cli"],
    )
    ws.task("web", "copy", dependencies=["task:homepage"])
    ws.task("web", "old", status="done", archived=True)
    ws.decision("web", "launch", dependencies=["task:copy"])
    ws.task("tooling", "docs", dependencies=["decision:web/launch"])
    return Graph.load(ws.workspace)


def test_nodes_and_statuses(sample):
    assert sample.status(task("web", "homepage")) == "todo"
    assert sample.status(decision("web", "design")) == "decided"
    assert sample.is_archived(task("web", "old"))
    assert task("web", "nope") not in sample
    assert str(task("web", "homepage")) == "task:web/homepage"


def test_satisfaction(sample):
    assert sample.is_satisfied(decision("web", "design"))
    assert sample.is_satisfied(task("web", "cms"))
    assert sample.is_satisfied(task("web", "old"))
    assert not sample.is_satisfied(task("tooling", "build-cli"))
    assert not sample.is_satisfied(decision("web", "launch"))
    assert not sample.is_satisfied(task("web", "nope"))


def test_dependency_statuses(sample):
    assert sample.dependency_statuses(task("web", "homepage")) == [
        DependencyStatus("decision:design", decision("web", "design"), "decided", True),
        DependencyStatus("task:cms", task("web", "cms"), "done", True),
        DependencyStatus("task:tooling/build-cli", task("tooling", "build-cli"), "in-progress", False),
    ]


def test_dependents(sample):
    assert sample.dependents(task("web", "homepage")) == [task("web", "copy")]
    assert sample.dependents(decision("web", "launch")) == [task("tooling", "docs")]
    assert sample.dependents(task("web", "cms")) == [task("web", "homepage")]
    assert sample.dependents(task("tooling", "docs")) == []


def test_ready_tasks(sample):
    # build-cli: no deps, in-progress -> ready; homepage: build-cli unsatisfied;
    # copy: homepage unsatisfied; docs: launch pending; cms/old: done.
    assert sample.ready_tasks() == [task("tooling", "build-cli")]


def test_archived_tasks_are_never_ready(ws):
    ws.project("p")
    ws.task("p", "old", archived=True)
    assert Graph.load(ws.workspace).ready_tasks() == []


def test_new_task_without_dependencies_is_ready(ws):
    ws.project("p")
    ws.task("p", "a")
    assert Graph.load(ws.workspace).ready_tasks() == [task("p", "a")]


class TestCheckNewDependencies:
    def test_accepts_resolvable_acyclic_refs(self, sample):
        refs = sample.check_new_dependencies(task("web", "cms"), ["decision:design", "task:web/old"])
        assert [str(ref) for ref in refs] == ["decision:design", "task:web/old"]

    def test_unresolved(self, sample):
        with pytest.raises(ChreosError, match="'task:nope' does not resolve"):
            sample.check_new_dependencies(task("web", "cms"), ["task:nope"])

    def test_invalid_ref_hint(self, sample):
        with pytest.raises(ChreosError, match="did you mean 'task:cms'"):
            sample.check_new_dependencies(task("web", "copy"), ["cms"])

    def test_self_dependency(self, sample):
        with pytest.raises(ChreosError, match="cannot depend on itself"):
            sample.check_new_dependencies(task("web", "cms"), ["task:cms"])

    def test_cycle_is_refused_with_path(self, sample):
        # docs -> launch -> copy -> homepage; homepage -> docs closes the cycle
        with pytest.raises(ChreosError) as error:
            sample.check_new_dependencies(task("web", "homepage"), ["task:tooling/docs"])
        assert (
            "task:web/homepage -> task:tooling/docs -> decision:web/launch "
            "-> task:web/copy -> task:web/homepage"
        ) in str(error.value)

    def test_cycle_among_the_new_refs_themselves(self, ws):
        ws.project("p")
        ws.task("p", "a")
        ws.task("p", "b", dependencies=["task:a"])
        graph = Graph.load(ws.workspace)
        with pytest.raises(ChreosError, match="cycle"):
            graph.check_new_dependencies(task("p", "a"), ["task:b"])

    def test_new_item_not_yet_in_graph(self, sample):
        refs = sample.check_new_dependencies(task("web", "brand-new"), ["task:copy"])
        assert [str(ref) for ref in refs] == ["task:copy"]


class TestProblems:
    def test_broken_and_hand_edited_files(self, ws):
        ws.project("p")
        ws.task("p", "a", dependencies=["task:missing", "bare-name", "task:b"])
        ws.write("p/tasks/b/TASK.md", "not frontmatter")
        graph = Graph.load(ws.workspace)
        assert [failure.path.name for failure in graph.failures] == ["TASK.md"]
        assert task("p", "b") in graph
        assert graph.status(task("p", "b")) is None
        messages = [str(problem) for problem in graph.problems]
        assert any("task:missing" in m and "does not resolve" in m for m in messages)
        assert any("bare-name" in m for m in messages)
        statuses = graph.dependency_statuses(task("p", "a"))
        assert [s.satisfied for s in statuses] == [False, False, False]
        assert graph.ready_tasks() == []

    def test_find_cycles(self, ws):
        ws.project("p")
        ws.task("p", "a", dependencies=["task:b"])
        ws.task("p", "b", dependencies=["task:c"])
        ws.task("p", "c", dependencies=["task:a"])
        ws.task("p", "self", dependencies=["task:self"])
        ws.task("p", "free", dependencies=["task:a"])
        cycles = Graph.load(ws.workspace).find_cycles()
        assert cycles == [
            [task("p", "a"), task("p", "b"), task("p", "c")],
            [task("p", "self")],
        ]

    def test_identity_comes_from_the_path_not_the_cache(self, ws):
        ws.project("p")
        path = ws.task("p", "real")
        path.write_text(path.read_text().replace("name: real", "name: stale"))
        graph = Graph.load(ws.workspace)
        assert task("p", "real") in graph
        assert task("p", "stale") not in graph


def test_long_chains_do_not_hit_the_recursion_limit():
    graph = Graph()
    from chreos.graph import _Entry

    nodes = [task("p", f"t{i}") for i in range(3000)]
    for node in nodes:
        graph._entries[node] = _Entry(path=None, archived=False, status="new")
    for current, following in zip(nodes, nodes[1:]):
        graph._entries[current].edges.append((f"task:{following.name}", following))
    graph._entries[nodes[-1]].edges.append(("task:t0", nodes[0]))
    assert graph.find_cycles() == [sorted(nodes)]


def test_statuses_for_arbitrary_refs(sample):
    assert sample.statuses_for("web", ["task:cms", "task:nope", "bad ref"]) == [
        DependencyStatus("task:cms", task("web", "cms"), "done", True),
        DependencyStatus("task:nope", None, None, False),
        DependencyStatus("bad ref", None, None, False),
    ]
