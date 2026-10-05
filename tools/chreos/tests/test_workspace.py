import pytest

from chreos.errors import ChreosError
from chreos.model import Kind
from chreos.refs import parse_ref
from chreos.workspace import Located, Workspace


class TestPaths:
    def test_layout(self, ws):
        w, root = ws.workspace, ws.root
        assert w.project_file("p") == root / "p" / "PROJECT.md"
        assert w.live_task_file("p", "t") == root / "p" / "tasks" / "t" / "TASK.md"
        assert w.archived_task_file("p", "t") == root / "p" / ".archive" / "t.md"
        assert w.decision_file("p", "d") == root / "p" / "decisions" / "d.md"
        assert w.lock_file == root / ".scepsis.lock"

    @pytest.mark.parametrize("name", ["..", "a/b", "/etc", "", "A"])
    def test_names_are_validated_before_building_paths(self, ws, name):
        w = ws.workspace
        for call in (
            lambda: w.project_dir(name),
            lambda: w.live_task_file("p", name),
            lambda: w.live_task_file(name, "t"),
            lambda: w.archived_task_file("p", name),
            lambda: w.decision_file("p", name),
        ):
            with pytest.raises(ChreosError, match="invalid name"):
                call()


class TestDiscovery:
    def test_projects(self, ws):
        ws.project("b-project")
        ws.project("a-project")
        ws.write("not-a-project/readme.md", "x")
        ws.write(".hidden/PROJECT.md", "x")
        ws.write("Bad_Name/PROJECT.md", "x")
        ws.write("file.md", "x")
        (ws.root / ".scepsis.lock").touch()
        assert ws.workspace.projects() == ["a-project", "b-project"]

    def test_tasks_live_and_archived(self, ws):
        ws.project("p")
        ws.task("p", "b")
        ws.task("p", "a")
        ws.task("p", "old", archived=True)
        ws.write("p/tasks/no-task-file/notes.md", "x")
        ws.write("p/tasks/stray.md", "x")
        ws.write("p/.archive/Bad.md", "x")
        ws.write("p/.archive/folder/x.md", "x")
        w = ws.workspace
        assert w.task_names("p") == ["a", "b"]
        assert w.task_names("p", archived=True) == ["old"]

    def test_decisions(self, ws):
        ws.project("p")
        ws.decision("p", "d2")
        ws.decision("p", "d1")
        ws.write("p/decisions/readme.txt", "x")
        assert ws.workspace.decision_names("p") == ["d1", "d2"]

    def test_missing_subfolders_are_empty(self, ws):
        ws.write("p/PROJECT.md", "x")
        w = ws.workspace
        assert w.task_names("p") == []
        assert w.task_names("p", archived=True) == []
        assert w.decision_names("p") == []

    def test_ensure_project_dirs_recreates_missing_folders(self, ws):
        ws.write("p/PROJECT.md", "x")
        ws.workspace.ensure_project_dirs("p")
        for folder in ("tasks", ".archive", "decisions"):
            assert (ws.root / "p" / folder).is_dir()

    def test_missing_workspace_root(self, tmp_path):
        assert Workspace(tmp_path / "nope").projects() == []


class TestUniqueness:
    def test_exists(self, ws):
        ws.project("p")
        ws.task("p", "live")
        ws.task("p", "old", archived=True)
        ws.decision("p", "d")
        w = ws.workspace
        assert w.project_exists("p") and not w.project_exists("q")
        assert w.task_exists("p", "live") and w.task_exists("p", "old")
        assert not w.task_exists("p", "d")
        assert w.decision_exists("p", "d") and not w.decision_exists("p", "live")

    def test_ensure_free(self, ws):
        ws.project("p")
        ws.task("p", "old", archived=True)
        ws.decision("p", "d")
        w = ws.workspace
        with pytest.raises(ChreosError, match="project 'p' already exists"):
            w.ensure_free(Kind.PROJECT, None, "p")
        with pytest.raises(ChreosError, match="task 'p/old' already exists \\(archived\\)"):
            w.ensure_free(Kind.TASK, "p", "old")
        with pytest.raises(ChreosError, match="decision 'p/d' already exists"):
            w.ensure_free(Kind.DECISION, "p", "d")
        w.ensure_free(Kind.TASK, "p", "d")  # separate namespaces
        w.ensure_free(Kind.DECISION, "p", "old")


class TestItemNames:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [("t", ("default", "t")), ("other/t", ("other", "t"))],
    )
    def test_parse_item_name(self, ws, text, expected):
        assert ws.workspace.parse_item_name(text, "default") == expected

    @pytest.mark.parametrize("text", ["task:t", "a/b/c", "T", "/t", "p/"])
    def test_invalid_item_names(self, ws, text):
        with pytest.raises(ChreosError):
            ws.workspace.parse_item_name(text, "default")


class TestResolve:
    def test_task_live_then_archived(self, ws):
        ws.project("p")
        live = ws.task("p", "live")
        old = ws.task("p", "old", archived=True)
        w = ws.workspace
        assert w.resolve(parse_ref("task:live"), "p") == Located(Kind.TASK, "p", "live", live, False)
        assert w.resolve(parse_ref("task:p/old"), "q") == Located(Kind.TASK, "p", "old", old, True)

    def test_decision(self, ws):
        ws.project("p")
        path = ws.decision("p", "d")
        assert ws.workspace.resolve(parse_ref("decision:d"), "p") == Located(Kind.DECISION, "p", "d", path, False)

    def test_unresolved(self, ws):
        ws.project("p")
        ws.task("p", "t")
        w = ws.workspace
        assert w.resolve(parse_ref("decision:t"), "p") is None
        assert w.resolve(parse_ref("task:t"), "q") is None
        assert w.resolve(parse_ref("task:nope"), "p") is None
