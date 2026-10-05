"""End-to-end: one workspace driven through every command group via the CLI only.

Extend this scenario when adding commands: it covers how commands interact
(lock, references, lifecycle, check), which the per-module tests don't.
"""

import json
import subprocess
import sys

import pytest

from chreos import cli_support
from conftest import git
from conftest import run_cli as run


def ok(*args, input=None):
    result = run(*args, input=input)
    assert result.exit_code == 0, f"{args}\n{result.stdout}\n{result.stderr}"
    return result


def fails(*args, contains):
    result = run(*args)
    assert result.exit_code == 1, f"{args} should fail\n{result.stdout}"
    assert contains in result.stderr, result.stderr
    return result


def as_json(*args):
    return json.loads(ok(*args, "--json").stdout)


def assert_clean():
    report = as_json("check")
    assert report["findings"] == [], report["findings"]


def deps(name):
    return [d["ref"] for d in as_json("task", "show", name)["dependencies"]]


@pytest.fixture
def home(tmp_path, monkeypatch, git_env):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(cli_support, "is_interactive", lambda: False)
    site = tmp_path / "code" / "site"
    site.mkdir(parents=True)
    git(site, "init", "-q", "-b", "main")
    (site / "README.md").write_text("site\n")
    git(site, "add", ".")
    git(site, "commit", "-q", "-m", "init")
    (tmp_path / "files").mkdir()
    return tmp_path


def test_full_workflow(home):
    ws = home / "ws"
    site = home / "code" / "site"

    # 1. Setup
    ok("init", "--workspace-path", "~/ws", "--source-git-path", "~/code")
    assert ok("config", "get", "source.git_path").stdout == "~/code\n"
    ok("config", "set", "output.format", "json")
    assert json.loads(ok("project", "list").stdout)[0]["name"] == "default"
    ok("config", "set", "output.format", "none")
    assert_clean()

    # 2. Items with mixed cross-project dependencies
    ok("project", "create", "web", "-t", "Website")
    ok("project", "create", "tooling")
    ok("project", "description", "replace", "web", input="Relaunch.\n\n### Goals\n\nFast pages.\n")
    ok("task", "create", "build-cli", "-P", "tooling", "--source-type", "git", "--source-path", "site", "--priority", "high")
    ok("task", "create", "cost-estimate", "-P", "web")
    ok("decision", "create", "hosting", "-P", "web", "--dep", "task:cost-estimate")
    ok("decision", "description", "replace", "web/hosting", input="### Options\n\n- A\n- B\n")
    assert ok("decision", "description", "show", "web/hosting").stdout == "### Options\n\n- A\n- B\n"
    ok("task", "create", "homepage", "-P", "web", "--source-type", "local", "--source-path", str(home / "files"),
       "--dep", "task:tooling/build-cli", "--dep", "decision:hosting")
    ok("task", "create", "launch", "-P", "web", "--dep", "task:homepage")
    ok("task", "create", "inbox-item", "--dep", "task:web/cost-estimate")
    ok("task", "update", "web/cost-estimate", "--status", "done")
    ok("decision", "update", "web/hosting", "--status", "decided")
    assert_clean()

    # 3. Open: git task is todo, local task is on-hold (build-cli isn't done)
    work = ok("task", "open", "tooling/build-cli", "--assignee", "claude").stdout.strip()
    assert git(work, "branch", "--show-current") == "build-cli"
    ok("task", "open", "web/homepage")
    statuses = {t["name"]: t["status"] for t in as_json("task", "list", "--all-projects", "--all")}
    assert statuses["build-cli"] == "todo" and statuses["homepage"] == "on-hold"
    ready = [t["name"] for t in as_json("task", "list", "--all-projects", "--ready")]
    assert ready == ["inbox-item", "build-cli"]  # sorted by project, then name
    assert_clean()

    # 4. Sections
    ok("task", "description", "append", "tooling/build-cli", "Package the CLI.")
    ok("task", "ac", "append", "tooling/build-cli", "-a", "Builds", "-a", "Reviewed by a human")
    ok("task", "refs", "append", "tooling/build-cli", "-r", "[Docs](https://docs.example)", "-r", "task:web/homepage")
    ok("task", "notes", "append", "tooling/build-cli", "-N", "Scaffolding done")
    fails("task", "refs", "append", "tooling/build-cli", "-r", "homepage", contains="did you mean")
    assert [r["kind"] for r in as_json("task", "refs", "show", "tooling/build-cli")] == ["link", "item"]

    # 5. Close: unchecked criteria and the dirty worktree are both guarded
    (ws / "tooling/tasks/build-cli/work/cli.py").write_text("print('hi')\n")
    git(work, "add", "cli.py")
    git(work, "commit", "-q", "-m", "cli")
    (ws / "tooling/tasks/build-cli/work/scratch.txt").write_text("tmp")
    fails("task", "close", "tooling/build-cli", "--status", "done", contains="2 unchecked acceptance criteria")
    ok("task", "ac", "check", "tooling/build-cli", "1", "2")
    fails("task", "close", "tooling/build-cli", "--status", "done", contains="scratch.txt")
    assert (ws / "tooling/tasks/build-cli/work/scratch.txt").exists()
    ok("task", "close", "tooling/build-cli", "--status", "done", "-f")
    assert not (ws / "tooling/tasks/build-cli/work").exists()
    assert "cli" in git(site, "log", "build-cli", "--format=%s")
    # statuses never change on their own (§11.5): check points at the now-unblocked task
    warnings = [f["message"] for f in as_json("check")["findings"] if f["severity"] == "warning"]
    assert warnings == ["the task is on-hold but all its dependencies are satisfied"]
    ok("task", "update", "web/homepage", "--status", "todo")
    assert_clean()

    # 6. Reopen reuses the branch
    work = ok("task", "open", "tooling/build-cli").stdout.strip()
    assert (ws / "tooling/tasks/build-cli/work/cli.py").exists()
    ok("task", "close", "tooling/build-cli", "--status", "done")
    assert_clean()

    # 7. Archive and restore
    ok("task", "archive", "tooling/build-cli")
    fails("task", "archive", "web/homepage", contains="close it first")
    ok("task", "archive", "web/homepage", "-f", "--status", "cancelled")
    assert (home / "files").is_dir()  # the local source folder is never touched
    fails("task", "update", "tooling/build-cli", "-t", "x", contains="restore it first")
    ok("task", "restore", "web/homepage")
    assert [t["name"] for t in as_json("task", "list", "-P", "tooling", "--archived", "--all")] == ["build-cli"]
    assert_clean()

    # 8. Move and rename: references follow in both directions
    ok("task", "move", "web/launch", "tooling")
    assert deps("tooling/launch") == ["task:web/homepage"]
    ok("decision", "move", "web/hosting", "tooling")
    assert deps("web/homepage") == ["task:tooling/build-cli", "decision:tooling/hosting"]
    assert [d["ref"] for d in as_json("decision", "show", "tooling/hosting")["dependencies"]] == ["task:web/cost-estimate"]
    ok("project", "rename", "web", "website")
    assert deps("tooling/launch") == ["task:website/homepage"]
    ok("project", "rename", "default", "inbox")
    assert ok("config", "get", "defaults.project").stdout == "inbox\n"
    assert deps("inbox-item") == ["task:website/cost-estimate"]
    assert_clean()

    # 9. Delete: references are removed from the remaining items
    ok("project", "create", "scratch")
    ok("task", "create", "spike", "-P", "scratch")
    ok("task", "update", "website/homepage", "--dep", "task:scratch/spike")
    fails("decision", "delete", "tooling/hosting", contains="task:website/homepage")
    ok("decision", "delete", "tooling/hosting", "-f")
    fails("project", "delete", "inbox", "-f", contains="default project")
    ok("project", "delete", "scratch", "-f")
    assert deps("website/homepage") == ["task:tooling/build-cli"]
    assert_clean()

    # 10. Final state
    tasks = {(t["project"], t["name"]): (t["phase"], t["status"]) for t in as_json("task", "list", "--all-projects", "--all")}
    assert tasks == {
        ("inbox", "inbox-item"): ("closed", "new"),
        ("tooling", "launch"): ("closed", "new"),
        ("website", "cost-estimate"): ("closed", "done"),
        ("website", "homepage"): ("closed", "cancelled"),
    }


def test_real_entry_point(tmp_path):
    env = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}

    def chreos(*args):
        return subprocess.run([sys.executable, "-m", "chreos", *args], capture_output=True, text=True, env=env)

    version = chreos("--version")
    assert version.returncode == 0 and version.stdout.startswith("chreos ")
    assert chreos("bogus").returncode == 2
    missing = chreos("config", "show")
    assert missing.returncode == 1 and "chreos init" in missing.stderr and "Traceback" not in missing.stderr
