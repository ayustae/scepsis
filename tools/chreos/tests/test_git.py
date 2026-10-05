import pytest

from chreos import git as g
from chreos.git import GitError, parse_version
from conftest import git


class TestVersion:
    @pytest.mark.parametrize(
        ("text", "version"),
        [
            ("git version 2.34.1", (2, 34, 1)),
            ("git version 2.39.2 (Apple Git-143)", (2, 39, 2)),
            ("git version 2.45.1.windows.1", (2, 45, 1)),
            ("git version 2.30.0\n", (2, 30, 0)),
        ],
    )
    def test_parse(self, text, version):
        assert parse_version(text) == version

    def test_unparseable(self):
        with pytest.raises(GitError, match="unexpected"):
            parse_version("nonsense")

    def test_too_old(self, monkeypatch):
        monkeypatch.setattr(g, "_installed_version", lambda: (2, 29, 9))
        g.check_version.cache_clear()
        try:
            with pytest.raises(GitError, match="2.30"):
                g.check_version()
        finally:
            g.check_version.cache_clear()

    def test_missing_git(self, monkeypatch):
        monkeypatch.setenv("PATH", "")
        with pytest.raises(GitError, match="git is not installed"):
            g.run(["--version"])

    def test_installed_git_is_supported(self):
        g.check_version()


def test_run_error_carries_stderr(git_repo):
    with pytest.raises(GitError, match="bogus"):
        g.run(["rev-parse", "--verify", "bogus"], cwd=git_repo)


def test_toplevel(git_repo):
    sub = git_repo / "sub"
    sub.mkdir()
    assert g.toplevel(sub) == git_repo


def test_toplevel_outside_a_repository(tmp_path, git_env):
    with pytest.raises(GitError):
        g.toplevel(tmp_path)


def test_branch_exists(git_repo):
    assert g.branch_exists(git_repo, "main")
    assert not g.branch_exists(git_repo, "nope")


def test_default_base(git_repo, cloned_repo):
    assert g.default_base(git_repo) == "HEAD"
    assert g.default_base(cloned_repo) == "origin/HEAD"


class TestWorktrees:
    def test_add_new_branch_from_base(self, git_repo, tmp_path):
        work = tmp_path / "task" / "work"
        work.parent.mkdir()
        g.worktree_add(git_repo, work, "my-task", "main")
        assert git(work, "branch", "--show-current") == "my-task"
        assert (work / "README.md").exists()
        assert g.checked_out_at(git_repo, "my-task") == work

    def test_add_existing_branch_keeps_its_commits(self, git_repo, tmp_path):
        git(git_repo, "branch", "my-task")
        work = tmp_path / "work"
        g.worktree_add(git_repo, work, "my-task", "main")
        (work / "f.txt").write_text("x")
        git(work, "add", ".")
        git(work, "commit", "-q", "-m", "work")
        g.worktree_remove(work, force=False)
        assert not work.exists()
        assert g.branch_exists(git_repo, "my-task")
        g.worktree_add(git_repo, work, "my-task", "main")
        assert (work / "f.txt").exists()

    def test_checked_out_at(self, git_repo):
        assert g.checked_out_at(git_repo, "main") == git_repo
        assert g.checked_out_at(git_repo, "nope") is None

    def test_dirty_files(self, git_repo, tmp_path):
        work = tmp_path / "work"
        g.worktree_add(git_repo, work, "t", "main")
        assert g.dirty_files(work) == []
        (work / "README.md").write_text("changed")
        (work / "new").mkdir()
        (work / "new" / "file.txt").write_text("x")
        assert g.dirty_files(work) == ["M README.md", "?? new/file.txt"]

    def test_remove_dirty_needs_force(self, git_repo, tmp_path):
        work = tmp_path / "work"
        g.worktree_add(git_repo, work, "t", "main")
        (work / "untracked").write_text("x")
        with pytest.raises(GitError):
            g.worktree_remove(work, force=False)
        g.worktree_remove(work, force=True)
        assert not work.exists()
        assert g.checked_out_at(git_repo, "t") is None

    def test_prune_after_hand_removal(self, git_repo, tmp_path):
        import shutil

        work = tmp_path / "work"
        g.worktree_add(git_repo, work, "t", "main")
        shutil.rmtree(work)
        g.worktree_prune(git_repo)
        assert g.checked_out_at(git_repo, "t") is None

    def test_is_worktree(self, git_repo, tmp_path):
        work = tmp_path / "work"
        g.worktree_add(git_repo, work, "t", "main")
        assert g.is_worktree(work)
        assert not g.is_worktree(tmp_path)


def test_base_cannot_look_like_an_option(git_repo, tmp_path):
    with pytest.raises(GitError, match="invalid base"):
        g.worktree_add(git_repo, tmp_path / "work", "t", "--orphan")


def test_rename_branch(git_repo):
    git(git_repo, "branch", "old")
    g.rename_branch(git_repo, "old", "new")
    assert g.branch_exists(git_repo, "new") and not g.branch_exists(git_repo, "old")


def test_worktree_repair_after_moving_it(git_repo, tmp_path):
    work = tmp_path / "a" / "work"
    work.parent.mkdir()
    g.worktree_add(git_repo, work, "t", "main")
    (tmp_path / "a").rename(tmp_path / "b")
    moved = tmp_path / "b" / "work"
    g.worktree_repair(moved)
    assert g.checked_out_at(git_repo, "t") == moved
    assert git(moved, "status", "--porcelain") == ""
