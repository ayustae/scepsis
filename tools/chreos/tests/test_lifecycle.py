import os

import pytest

from chreos import git as g
from chreos.errors import ChreosError
from chreos.frontmatter import load
from chreos.graph import Graph
from chreos.lifecycle import close_task, cleanup, losses, open_task
from chreos.model import SourceType
from conftest import git

BASES = {SourceType.GIT: None, SourceType.LOCAL: None}


@pytest.fixture
def folder(tmp_path):
    path = tmp_path / "shared-folder"
    path.mkdir()
    (path / "keep.txt").write_text("precious")
    return path


def git_task(ws, repo, name="t", **kwargs):
    ws.project("p")
    return ws.task("p", name, source={"type": "git", "path": str(repo)}, **kwargs)


def local_task(ws, folder, name="t", **kwargs):
    ws.project("p")
    return ws.task("p", name, source={"type": "local", "path": str(folder)}, **kwargs)


def do_open(ws, name="t", confirm=None, **kwargs):
    return open_task(
        ws.workspace, Graph.load(ws.workspace), "p", name, bases=BASES,
        confirm=confirm or (lambda _: True), **kwargs,
    )


def do_close(ws, name="t", confirm=None, **kwargs):
    return close_task(
        ws.workspace, Graph.load(ws.workspace), "p", name,
        confirm=confirm or (lambda _: True), **kwargs,
    )


class TestOpenGit:
    def test_creates_worktree_on_task_branch(self, ws, git_repo):
        path = git_task(ws, git_repo)
        before = load(path).meta["updated"]
        outcome = do_open(ws)
        work = path.parent / "work"
        assert g.is_worktree(work)
        assert git(work, "branch", "--show-current") == "t"
        meta = load(path).meta
        assert (meta["phase"], meta["status"]) == ("open", "todo")
        assert meta["updated"] >= before
        assert outcome.warnings == []

    def test_new_branch_from_origin_head(self, ws, git_repo, cloned_repo):
        git(cloned_repo, "commit", "-q", "--allow-empty", "-m", "local only")
        path = git_task(ws, cloned_repo)
        do_open(ws)
        log = git(path.parent / "work", "log", "--format=%s")
        assert "local only" not in log

    def test_explicit_base(self, ws, git_repo):
        git(git_repo, "checkout", "-q", "-b", "develop")
        git(git_repo, "commit", "-q", "--allow-empty", "-m", "on develop")
        git(git_repo, "checkout", "-q", "main")
        path = git_task(ws, git_repo)
        do_open(ws, base="develop")
        assert git(path.parent / "work", "log", "-1", "--format=%s") == "on develop"

    def test_branch_checked_out_elsewhere(self, ws, git_repo, tmp_path):
        git(git_repo, "worktree", "add", "-q", "-b", "t", str(tmp_path / "elsewhere"))
        path = git_task(ws, git_repo)
        with pytest.raises(ChreosError, match="already checked out at .*elsewhere"):
            do_open(ws)
        assert load(path).meta["phase"] == "closed"
        assert not (path.parent / "work").exists()

    def test_reopen_reuses_branch_and_commits(self, ws, git_repo):
        path = git_task(ws, git_repo)
        do_open(ws)
        work = path.parent / "work"
        (work / "f.txt").write_text("x")
        git(work, "add", ".")
        git(work, "commit", "-q", "-m", "work")
        do_close(ws, status="done")
        assert not work.exists()
        assert g.branch_exists(git_repo, "t")
        outcome = do_open(ws, status="in-progress")
        assert (work / "f.txt").exists()
        assert load(path).meta["status"] == "in-progress"
        assert outcome.warnings == []


class TestOpenStatus:
    def test_on_hold_when_dependencies_unsatisfied(self, ws, folder):
        local_task(ws, folder, dependencies=["task:other"])
        ws.task("p", "other", status="new")
        do_open(ws)
        assert load(ws.workspace.live_task_file("p", "t")).meta["status"] == "on-hold"

    def test_todo_when_dependencies_satisfied(self, ws, folder):
        local_task(ws, folder, dependencies=["task:other"])
        ws.task("p", "other", status="cancelled")
        do_open(ws)
        assert load(ws.workspace.live_task_file("p", "t")).meta["status"] == "todo"

    def test_explicit_status_must_be_allowed_when_open(self, ws, folder):
        local_task(ws, folder)
        with pytest.raises(ChreosError, match="not allowed in phase 'open'"):
            do_open(ws, status="new")

    def test_done_asks_for_confirmation(self, ws, folder, no):
        path = local_task(ws, folder, dependencies=["task:other"])
        ws.task("p", "other")
        with pytest.raises(ChreosError, match="cancelled"):
            do_open(ws, status="done", confirm=no)
        assert "task:other (new)" in no.messages[0]
        assert load(path).meta["phase"] == "closed"
        assert not (path.parent / "work").exists()


class TestOpenLocal:
    def test_symlink_to_folder(self, ws, folder):
        path = local_task(ws, folder)
        do_open(ws)
        work = path.parent / "work"
        assert work.is_symlink() and work.resolve() == folder.resolve()

    def test_relative_source_uses_base(self, ws, folder):
        ws.project("p")
        ws.task("p", "t", source={"type": "local", "path": folder.name})
        bases = {SourceType.LOCAL: folder.parent}
        open_task(ws.workspace, Graph.load(ws.workspace), "p", "t", bases=bases, confirm=lambda _: True)
        assert (ws.workspace.live_task_file("p", "t").parent / "work").resolve() == folder.resolve()

    def test_without_source(self, ws):
        ws.project("p")
        ws.task("p", "t")
        with pytest.raises(ChreosError, match="has no source"):
            do_open(ws)


class TestOpenWhenOpen:
    def test_recreates_missing_work(self, ws, folder):
        path = local_task(ws, folder)
        do_open(ws)
        (path.parent / "work").unlink()
        do_open(ws)
        assert (path.parent / "work").is_symlink()

    def test_status_applied_without_recomputing(self, ws, folder):
        path = local_task(ws, folder, dependencies=["task:other"])
        ws.task("p", "other")
        do_open(ws)
        do_open(ws, status="in-progress")
        assert load(path).meta["status"] == "in-progress"
        do_open(ws)
        assert load(path).meta["status"] == "in-progress"

    def test_recreate_with_safety_check(self, ws, git_repo, no, yes):
        path = git_task(ws, git_repo)
        do_open(ws)
        work = path.parent / "work"
        (work / "scratch.txt").write_text("x")
        (path.parent / "notes.md").write_text("mine")
        with pytest.raises(ChreosError, match="cancelled"):
            do_open(ws, recreate=True, confirm=no)
        assert (work / "scratch.txt").exists()
        assert "?? scratch.txt" in no.messages[0]
        assert "notes.md" not in no.messages[0]  # --recreate only touches work/
        do_open(ws, recreate=True, confirm=yes)
        assert g.is_worktree(work) and not (work / "scratch.txt").exists()
        assert (path.parent / "notes.md").exists()

    def test_recreate_repairs_a_broken_link(self, ws, folder, tmp_path):
        path = local_task(ws, folder)
        do_open(ws)
        work = path.parent / "work"
        work.unlink()
        work.symlink_to(tmp_path / "gone")
        do_open(ws, recreate=True)
        assert work.resolve() == folder.resolve()

    def test_archived_task_is_refused(self, ws):
        ws.project("p")
        ws.task("p", "t", archived=True)
        with pytest.raises(ChreosError, match="archived; restore it first"):
            do_open(ws)

    def test_missing_task(self, ws):
        ws.project("p")
        with pytest.raises(ChreosError, match="does not exist"):
            do_open(ws)


class TestClose:
    def test_requires_done_or_cancelled(self, ws, folder):
        path = local_task(ws, folder)
        do_open(ws)
        with pytest.raises(ChreosError, match="done or cancelled"):
            do_close(ws)
        with pytest.raises(ChreosError, match="done or cancelled"):
            do_close(ws, status="todo")
        assert load(path).meta["phase"] == "open"

    def test_local_close_keeps_target_untouched(self, ws, folder):
        path = local_task(ws, folder)
        do_open(ws)
        do_close(ws, status="cancelled")
        assert sorted(os.listdir(path.parent)) == ["TASK.md"]
        assert (folder / "keep.txt").read_text() == "precious"
        meta = load(path).meta
        assert (meta["phase"], meta["status"]) == ("closed", "cancelled")

    def test_done_confirmation_counts_criteria(self, ws, folder, no):
        path = local_task(ws, folder)
        text = path.read_text().replace("## Acceptance criteria\n", "## Acceptance criteria\n\n- [ ] a\n- [x] b\n")
        path.write_text(text)
        do_open(ws)
        with pytest.raises(ChreosError, match="cancelled"):
            do_close(ws, status="done", confirm=no)
        assert "1 unchecked acceptance criterion" in no.messages[0]
        assert load(path).meta["phase"] == "open"

    def test_already_done_status_closes_without_status(self, ws, folder):
        path = local_task(ws, folder)
        do_open(ws, status="done")
        do_close(ws)
        assert load(path).meta["phase"] == "closed"

    def test_dirty_worktree_and_extra_files(self, ws, git_repo, no, yes):
        path = git_task(ws, git_repo)
        do_open(ws)
        work = path.parent / "work"
        (work / "README.md").write_text("changed")
        (path.parent / "artifact.bin").write_text("x")
        (path.parent / "out").mkdir()
        with pytest.raises(ChreosError, match="cancelled"):
            do_close(ws, status="done", confirm=no)
        message = no.messages[0]
        assert "work/: M README.md" in message and "artifact.bin" in message and "out/" in message
        assert load(path).meta["phase"] == "open"
        assert (work / "README.md").read_text() == "changed"
        do_close(ws, status="done", confirm=yes)
        assert sorted(os.listdir(path.parent)) == ["TASK.md"]
        assert g.branch_exists(git_repo, "t")
        assert g.checked_out_at(git_repo, "t") is None

    def test_clean_close_does_not_ask(self, ws, git_repo, no):
        path = git_task(ws, git_repo)
        do_open(ws)
        do_close(ws, status="cancelled", confirm=no)
        assert no.messages == []
        assert load(path).meta["phase"] == "closed"

    def test_reclose_only_cleans_up_and_warns_about_status(self, ws, folder):
        path = local_task(ws, folder, status="done")
        (path.parent / "leftover.txt").write_text("x")
        before = path.read_text()
        outcome = do_close(ws, status="cancelled")
        assert sorted(os.listdir(path.parent)) == ["TASK.md"]
        assert path.read_text() == before
        assert outcome.warnings == ["--status ignored: the task is already closed"]


@pytest.fixture
def task_dir(tmp_path):
    path = tmp_path / "task"
    path.mkdir()
    (path / "TASK.md").write_text("x")
    return path


class TestLossesAndCleanup:
    def test_symlinked_work_is_never_a_loss(self, task_dir, folder):
        (task_dir / "work").symlink_to(folder)
        assert losses(task_dir) == []
        cleanup(task_dir, lambda _: False)
        assert os.listdir(task_dir) == ["TASK.md"]
        assert (folder / "keep.txt").exists()

    def test_plain_work_folder_is_a_loss(self, task_dir, git_env):
        (task_dir / "work").mkdir()
        assert losses(task_dir) == ["work/ (not a git worktree or link)"]

    def test_symlinked_extra_entries_are_removed_without_following(self, task_dir, folder):
        (task_dir / "link").symlink_to(folder)
        assert losses(task_dir) == ["link"]
        cleanup(task_dir, lambda _: True)
        assert os.listdir(task_dir) == ["TASK.md"]
        assert (folder / "keep.txt").exists()

    def test_refused_cleanup_removes_nothing(self, task_dir):
        (task_dir / "notes.md").write_text("x")
        with pytest.raises(ChreosError, match="cancelled"):
            cleanup(task_dir, lambda _: False)
        assert sorted(os.listdir(task_dir)) == ["TASK.md", "notes.md"]


class TestOpenAssignee:
    def test_assigns_in_the_same_write(self, ws, folder):
        path = local_task(ws, folder)
        do_open(ws, assignee="claude")
        assert load(path).meta["assignee"] == "claude"

    def test_refused_reassignment_changes_nothing(self, ws, folder, no):
        path = local_task(ws, folder, assignee="alice")
        with pytest.raises(ChreosError, match="cancelled"):
            do_open(ws, assignee="bob", confirm=no)
        assert "alice" in no.messages[0]
        assert not (path.parent / "work").exists()
        assert load(path).meta["phase"] == "closed"
