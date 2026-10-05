import pytest

from chreos import git as g
from chreos.frontmatter import load
from conftest import git
from conftest import run_cli as run


def ok(*args, input=None):
    result = run(*args, input=input)
    assert result.exit_code == 0, result.output + result.stderr
    return result


@pytest.fixture
def ws_root(cli_home, git_repo, tmp_path):
    # git_repo lives at tmp_path/"repo"; make tmp_path the git base folder
    ok("config", "set", "source.git_path", str(tmp_path))
    ok("project", "create", "web")
    ok("task", "create", "feature", "-P", "web", "--source-type", "git", "--source-path", "repo")
    folder = tmp_path / "files"
    folder.mkdir()
    ok("task", "create", "notes", "-P", "web", "--source-type", "local", "--source-path", str(folder))
    return cli_home / "ws"


def meta(ws_root, project, name, archived=False):
    path = ws_root / project / (f".archive/{name}.md" if archived else f"tasks/{name}/TASK.md")
    return load(path).meta


class TestOpenClose:
    def test_git_task_round_trip(self, ws_root, git_repo):
        result = ok("task", "open", "web/feature", "--assignee", "claude")
        work = ws_root / "web/tasks/feature/work"
        assert result.stdout.strip() == str(work)
        assert "todo" in result.stderr
        assert git(work, "branch", "--show-current") == "feature"
        assert (meta(ws_root, "web", "feature")["assignee"]) == "claude"
        (work / "scratch.txt").write_text("x")
        result = run("task", "close", "web/feature", "--status", "done")
        assert result.exit_code == 1 and "scratch.txt" in result.stderr
        assert work.exists()
        ok("task", "close", "web/feature", "--status", "done", "-f")
        assert not work.exists() and g.branch_exists(git_repo, "feature")
        assert (meta(ws_root, "web", "feature")["phase"], meta(ws_root, "web", "feature")["status"]) == ("closed", "done")

    def test_open_status_recreate_and_errors(self, ws_root):
        ok("task", "open", "web/notes", "--status", "in-progress")
        assert meta(ws_root, "web", "notes")["status"] == "in-progress"
        ok("task", "open", "web/notes", "--recreate", "-f")
        assert (ws_root / "web/tasks/notes/work").is_symlink()
        result = run("task", "close", "web/notes")
        assert result.exit_code == 1 and "done or cancelled" in result.stderr
        ok("task", "create", "nosource", "-P", "web")
        result = run("task", "open", "web/nosource")
        assert result.exit_code == 1 and "no source" in result.stderr


class TestOperations:
    def test_archive_restore(self, ws_root):
        ok("task", "update", "web/notes", "--status", "cancelled")
        ok("task", "archive", "web/notes")
        assert meta(ws_root, "web", "notes", archived=True)["archived"] is not None
        for args in (["update", "web/notes", "-t", "x"], ["open", "web/notes"], ["ac", "append", "web/notes", "-a", "x"]):
            result = run("task", *args)
            assert result.exit_code == 1 and "restore it first" in result.stderr, args
        ok("task", "restore", "web/notes")
        assert "archived" not in meta(ws_root, "web", "notes")

    def test_archive_open_task(self, ws_root):
        ok("task", "open", "web/notes")
        result = run("task", "archive", "web/notes")
        assert result.exit_code == 1 and "close it first" in result.stderr
        ok("task", "archive", "web/notes", "-f", "--status", "cancelled")
        assert meta(ws_root, "web", "notes", archived=True)["status"] == "cancelled"

    def test_delete_rename_move(self, ws_root, git_repo):
        ok("project", "create", "other")
        ok("task", "create", "holder", "-P", "other", "--dep", "task:web/feature", "--dep", "task:web/notes")
        git(git_repo, "branch", "feature")
        ok("task", "rename", "web/feature", "feature-two")
        assert g.branch_exists(git_repo, "feature-two")
        ok("task", "move", "web/feature-two", "other")
        assert meta(ws_root, "other", "holder")["dependencies"] == ["task:feature-two", "task:web/notes"]
        result = run("task", "delete", "web/notes")
        assert result.exit_code == 1 and "task:other/holder" in result.stderr
        ok("task", "delete", "web/notes", "-f")
        assert meta(ws_root, "other", "holder")["dependencies"] == ["task:feature-two"]
