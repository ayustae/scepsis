import json
from datetime import date, timedelta

import pytest

from chreos.frontmatter import load
from conftest import run_cli as run


def ok(*args, input=None):
    result = run(*args, input=input)
    assert result.exit_code == 0, result.output + result.stderr
    return result


@pytest.fixture
def ws_root(cli_home):
    ok("project", "create", "web")
    ok("project", "create", "tooling")
    return cli_home / "ws"


class TestCreateUpdate:
    def test_create_in_default_and_named_project(self, ws_root):
        assert ok("task", "create", "inbox-item").output.strip() == str(ws_root / "default/tasks/inbox-item/TASK.md")
        ok("task", "create", "cli", "-P", "tooling", "--priority", "high")
        ok("task", "create", "web/homepage", "-t", "Homepage", "--dep", "task:tooling/cli", "--depends-on", "task:default/inbox-item",
           "--due", "2026-10-15", "--assignee", "claude", "-l", "urgent", "--source-type", "local", "--source-path", str(ws_root))
        meta = load(ws_root / "web/tasks/homepage/TASK.md").meta
        assert list(meta["dependencies"]) == ["task:tooling/cli", "task:default/inbox-item"]
        assert meta["assignee"] == "claude" and meta["due"] == date(2026, 10, 15)

    def test_create_warnings_and_errors(self, ws_root):
        result = ok("task", "create", "t", "--source-type", "git", "--source-path", "relative")
        assert "warning:" in result.stderr and "source.git_path" in result.stderr
        assert run("task", "create", "t2", "--dep", "missing").exit_code == 1
        assert run("task", "create", "t3", "--priority", "urgent").exit_code == 2
        assert run("task", "create", "web/t4", "-P", "tooling").exit_code == 1

    def test_update(self, ws_root):
        ok("task", "create", "t", "--assignee", "alice")
        path = ws_root / "default/tasks/t/TASK.md"
        result = run("task", "update", "t", "--assignee", "bob")
        assert result.exit_code == 1 and "confirmation required" in result.stderr
        ok("task", "update", "t", "--assignee", "bob", "-f", "--priority", "low", "--status", "cancelled")
        meta = load(path).meta
        assert (meta["assignee"], meta["priority"], meta["status"]) == ("bob", "low", "cancelled")
        assert run("task", "update", "t").exit_code == 2
        result = run("task", "update", "t", "--status", "todo")
        assert result.exit_code == 1 and "task open" in result.stderr

    def test_update_done_needs_confirmation(self, ws_root):
        ok("task", "create", "blocker")
        ok("task", "create", "t", "--dep", "task:blocker")
        path = ws_root / "default/tasks/t/TASK.md"
        path.write_text(path.read_text().replace("phase: closed", "phase: open").replace("status: new", "status: todo"))
        assert run("task", "update", "t", "--status", "done").exit_code == 1
        ok("task", "update", "t", "--status", "done", "-f")
        assert load(path).meta["status"] == "done"

    def test_update_deps_and_cycle(self, ws_root):
        ok("task", "create", "a")
        ok("task", "create", "b", "--dep", "task:a")
        result = run("task", "update", "a", "--dep", "task:b")
        assert result.exit_code == 1 and "cycle" in result.stderr
        result = ok("task", "update", "b", "--remove-dep", "task:default/a", "--remove-dep", "task:zzz")
        assert "task:zzz" in result.stderr
        assert list(load(ws_root / "default/tasks/b/TASK.md").meta["dependencies"]) == []


class TestReading:
    @pytest.fixture(autouse=True)
    def tasks(self, ws_root):
        today = date.today()
        ok("task", "create", "blocker", "-P", "web", "--priority", "low")
        ok("task", "create", "homepage", "-P", "web", "--dep", "task:blocker", "--priority", "critical",
           "--due", str(today + timedelta(days=30)), "--assignee", "claude")
        ok("task", "create", "late", "-P", "web", "--due", str(today - timedelta(days=1)), "--priority", "high")
        ok("task", "create", "finished", "-P", "web")
        ok("task", "update", "web/finished", "--status", "done", "-f")
        ok("task", "create", "cli", "-P", "tooling", "--dep", "task:web/homepage")

    def names(self, *args):
        return [line.split()[0] for line in ok("task", "list", *args).output.splitlines()]

    def test_list_scopes_and_default_status(self):
        assert self.names("-P", "web") == ["blocker", "homepage", "late"]
        assert self.names("-P", "web", "--all") == ["blocker", "finished", "homepage", "late"]
        assert self.names() == []  # default project is empty
        assert self.names("--all-projects") == ["tooling/cli", "web/blocker", "web/homepage", "web/late"]

    def test_list_filters(self):
        a = ("--all-projects",)
        assert self.names(*a, "--ready") == ["web/blocker", "web/late"]
        assert self.names(*a, "--unassigned", "--sort", "priority") == ["web/late", "web/blocker", "tooling/cli"]
        assert self.names(*a, "--overdue") == ["web/late"]
        assert self.names(*a, "--assignee", "claude") == ["web/homepage"]
        assert self.names(*a, "--priority", "low", "--priority", "high") == ["web/blocker", "web/late"]
        assert self.names(*a, "--phase", "closed", "--status", "done") == ["web/finished"]
        assert self.names(*a, "--due-before", "2999-01-01", "--sort", "due") == ["web/late", "web/homepage"]
        assert self.names("-P", "web", "--depends-on", "task:blocker") == ["homepage"]
        assert self.names("-P", "tooling", "--depends-on", "task:web/homepage") == ["cli"]

    def test_list_json_and_archived(self, ws_root):
        data = json.loads(ok("task", "list", "-P", "web", "--json", "--sort", "priority").output)
        assert [entry["name"] for entry in data] == ["homepage", "late", "blocker"]
        assert data[0]["dependencies"] == ["task:blocker"] and data[0]["path"].endswith("web/tasks/homepage/TASK.md")
        archived = ws_root / "web/.archive/old.md"
        archived.write_text((ws_root / "web/tasks/blocker/TASK.md").read_text().replace("name: blocker", "name: old"))
        assert self.names("-P", "web", "--archived", "--all") == ["old"]

    def test_show(self, ws_root):
        text = ok("task", "show", "web/homepage").output
        assert text.startswith("---\nname: homepage")
        assert "task:blocker  new  unsatisfied" in text and "task:tooling/cli" in text
        data = json.loads(ok("task", "show", "homepage", "-P", "web", "--json").output)
        assert data["dependencies"] == [{"ref": "task:blocker", "status": "new", "satisfied": False}]
        assert data["dependents"] == ["task:tooling/cli"]
        assert data["frontmatter"]["priority"] == "critical"

    def test_path(self, ws_root):
        assert ok("task", "path", "web/late").output.strip() == str(ws_root / "web/tasks/late/TASK.md")
        result = run("task", "path", "web/late", "--work")
        assert result.exit_code == 1 and "not open" in result.stderr
        assert run("task", "path", "web/nope").exit_code == 1

    def test_edit_requires_terminal(self):
        result = run("task", "edit", "web/late")
        assert result.exit_code == 1 and "see 'chreos task --help'" in result.stderr
