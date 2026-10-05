import json

import pytest

from chreos.frontmatter import load
from conftest import run_cli as run


def ok(*args):
    result = run(*args)
    assert result.exit_code == 0, result.output + result.stderr
    return result


@pytest.fixture
def ws_root(cli_home):
    ok("project", "create", "web")
    ok("task", "create", "research", "-P", "web")
    return cli_home / "ws"


def test_create_and_decided_confirmation(ws_root):
    path = ws_root / "web/decisions/hosting.md"
    assert ok("decision", "create", "hosting", "-P", "web", "-t", "Hosting", "--dep", "task:research").stdout.strip() == str(path)
    result = run("decision", "create", "cdn", "-P", "web", "--dep", "task:research", "--status", "decided")
    assert result.exit_code == 1 and "task:research (new)" in result.stderr
    ok("decision", "create", "cdn", "-P", "web", "--dep", "task:research", "--status", "decided", "-f")
    assert load(ws_root / "web/decisions/cdn.md").meta["status"] == "decided"


def test_update_makes_dependent_task_ready(ws_root):
    ok("decision", "create", "hosting", "-P", "web")
    ok("task", "create", "deploy", "-P", "web", "--dep", "decision:hosting")
    assert "deploy" not in ok("task", "list", "-P", "web", "--ready").stdout
    ok("decision", "update", "web/hosting", "--status", "decided", "-t", "Hosting", "-l", "area=infra")
    assert "deploy" in ok("task", "list", "-P", "web", "--ready").stdout
    assert run("decision", "update", "web/hosting").exit_code == 2
    result = run("decision", "update", "web/hosting", "--dep", "task:deploy")
    assert result.exit_code == 1 and "cycle" in result.stderr


def test_list(ws_root):
    ok("decision", "create", "a", "-P", "web", "--dep", "task:research")
    ok("decision", "create", "b", "-P", "web", "--status", "decided")
    ok("decision", "create", "c")
    names = lambda *a: [line.split()[0] for line in ok("decision", "list", *a).stdout.splitlines()]  # noqa: E731
    assert names("-P", "web") == ["a"]
    assert names("-P", "web", "--all") == ["a", "b"]
    assert names("--all-projects") == ["default/c", "web/a"]
    assert names("-P", "web", "--depends-on", "task:research") == ["a"]
    data = json.loads(ok("decision", "list", "-P", "web", "--all", "--json").stdout)
    assert [d["name"] for d in data] == ["a", "b"] and data[0]["dependencies"] == ["task:research"]


def test_show_path_edit(ws_root):
    ok("decision", "create", "hosting", "-P", "web", "--dep", "task:research")
    ok("task", "create", "deploy", "-P", "web", "--dep", "decision:hosting")
    text = ok("decision", "show", "web/hosting").stdout
    assert "task:research  new  unsatisfied" in text and "task:web/deploy" in text
    data = json.loads(ok("decision", "show", "web/hosting", "--json").stdout)
    assert data["dependents"] == ["task:web/deploy"] and data["dependencies"][0]["satisfied"] is False
    assert ok("decision", "path", "web/hosting").stdout.strip() == str(ws_root / "web/decisions/hosting.md")
    assert run("decision", "path", "web/nope").exit_code == 1
    assert run("decision", "edit", "web/hosting").exit_code == 1  # no terminal


def test_rename_move_delete_keep_references(ws_root):
    ok("project", "create", "infra")
    ok("decision", "create", "hosting", "-P", "web")
    ok("task", "create", "deploy", "-P", "web", "--dep", "decision:hosting")
    deploy = ws_root / "web/tasks/deploy/TASK.md"
    ok("decision", "rename", "web/hosting", "provider")
    assert load(deploy).meta["dependencies"] == ["decision:provider"]
    ok("decision", "move", "web/provider", "infra")
    assert load(deploy).meta["dependencies"] == ["decision:infra/provider"]
    result = run("decision", "delete", "infra/provider")
    assert result.exit_code == 1 and "task:web/deploy" in result.stderr
    ok("decision", "delete", "infra/provider", "-f")
    assert load(deploy).meta["dependencies"] == []
