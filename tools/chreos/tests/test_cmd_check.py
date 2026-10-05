import json

from conftest import run_cli as run


def test_clean_workspace(cli_home):
    result = run("check")
    assert result.exit_code == 0
    assert result.stdout == "no problems found\n"


def test_warnings_only_exit_0(cli_home):
    (cli_home / "ws" / "stray").mkdir()
    result = run("check")
    assert result.exit_code == 0
    assert result.stdout.splitlines()[0].startswith("warning  stray")
    assert result.stdout.splitlines()[-1] == "0 errors, 1 warning"


def test_errors_exit_1_and_json(cli_home):
    run("task", "create", "t", "--dep", "task:other")  # refused: doesn't resolve
    run("task", "create", "other")
    run("task", "create", "t", "--dep", "task:other")
    (cli_home / "ws/default/tasks/other").rename(cli_home / "ws/default/tasks/renamed")
    result = run("check")
    assert result.exit_code == 1
    lines = result.stdout.splitlines()
    assert lines[0].split()[:3] == ["error", "default/tasks/renamed/TASK.md", "task:default/renamed"]
    assert lines[-1] == "2 errors, 0 warnings"
    data = json.loads(run("check", "--json").stdout)
    assert data["errors"] == 2 and data["warnings"] == 0
    assert {f["message"].split(":")[0] for f in data["findings"]} >= {"name"}
    assert all(set(f) == {"severity", "path", "item", "message"} for f in data["findings"])


def test_fix(cli_home):
    run("task", "create", "other")
    (cli_home / "ws/default/tasks/other").rename(cli_home / "ws/default/tasks/renamed")
    result = run("check", "--fix")
    assert "fixed" in result.stderr and "renamed/TASK.md" in result.stderr
    assert result.exit_code == 0 and result.stdout == "no problems found\n"
