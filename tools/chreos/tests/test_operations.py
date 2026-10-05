import pytest

from chreos import git as g
from chreos.errors import ChreosError
from chreos.frontmatter import load
from chreos.graph import Graph
from chreos.lifecycle import open_task
from chreos.model import SourceType
from chreos.operations import (
    archive_task,
    delete_decision,
    delete_project,
    delete_task,
    move_decision,
    move_task,
    rename_decision,
    rename_project,
    rename_task,
    restore_task,
)
from conftest import git

BASES = {SourceType.GIT: None, SourceType.LOCAL: None}
YES = lambda _: True  # noqa: E731


def open_(ws, project, name):
    open_task(ws.workspace, Graph.load(ws.workspace), project, name, bases=BASES, confirm=YES)


def tree(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if ".scepsis.lock" not in str(p))


class TestArchiveRestore:
    def test_archive_closed_task(self, ws):
        ws.project("p")
        ws.task("p", "t", status="done")
        holder = ws.task("p", "h", dependencies=["task:t"])
        before = holder.read_text()
        archive_task(ws.workspace, Graph.load(ws.workspace), "p", "t", confirm=YES)
        assert not (ws.root / "p/tasks/t").exists()
        meta = load(ws.root / "p/.archive/t.md").meta
        assert meta["archived"] is not None and meta["status"] == "done"
        assert holder.read_text() == before

    def test_open_task_needs_force(self, ws, tmp_path):
        ws.project("p")
        ws.task("p", "t", source={"type": "local", "path": str(tmp_path)})
        open_(ws, "p", "t")
        with pytest.raises(ChreosError, match="close it first"):
            archive_task(ws.workspace, Graph.load(ws.workspace), "p", "t", confirm=YES)
        with pytest.raises(ChreosError, match="done or cancelled"):
            archive_task(ws.workspace, Graph.load(ws.workspace), "p", "t", confirm=YES, force=True)
        assert (ws.root / "p/tasks/t/work").is_symlink()
        archive_task(ws.workspace, Graph.load(ws.workspace), "p", "t", confirm=YES, force=True, status="cancelled")
        meta = load(ws.root / "p/.archive/t.md").meta
        assert (meta["phase"], meta["status"]) == ("closed", "cancelled")

    def test_leftover_files_need_confirmation(self, ws, no):
        ws.project("p")
        ws.task("p", "t")
        ws.write("p/tasks/t/leftover.txt", "x")
        with pytest.raises(ChreosError, match="cancelled"):
            archive_task(ws.workspace, Graph.load(ws.workspace), "p", "t", confirm=no)
        assert "leftover.txt" in no.messages[0]
        assert (ws.root / "p/tasks/t/TASK.md").exists()

    def test_archive_missing_or_archived(self, ws):
        ws.project("p")
        ws.task("p", "old", archived=True)
        with pytest.raises(ChreosError, match="already archived"):
            archive_task(ws.workspace, Graph.load(ws.workspace), "p", "old", confirm=YES)
        with pytest.raises(ChreosError, match="does not exist"):
            archive_task(ws.workspace, Graph.load(ws.workspace), "p", "nope", confirm=YES)

    def test_restore(self, ws):
        ws.project("p")
        ws.task("p", "t", archived=True, status="done")
        restore_task(ws.workspace, "p", "t")
        meta = load(ws.root / "p/tasks/t/TASK.md").meta
        assert "archived" not in meta and meta["phase"] == "closed"
        assert not (ws.root / "p/.archive/t.md").exists()

    def test_restore_refusals(self, ws):
        ws.project("p")
        ws.task("p", "live")
        with pytest.raises(ChreosError, match="not archived"):
            restore_task(ws.workspace, "p", "live")
        ws.write("p/.archive/live.md", (ws.root / "p/tasks/live/TASK.md").read_text())
        with pytest.raises(ChreosError, match="already exists"):
            restore_task(ws.workspace, "p", "live")


class TestRename:
    def test_live_task_with_references(self, ws):
        ws.project("p")
        ws.project("q")
        ws.task("p", "old")
        holder = ws.task("q", "h", dependencies=["task:p/old"])
        outcome = rename_task(ws.workspace, "p", "old", "new", bases=BASES)
        assert load(ws.root / "p/tasks/new/TASK.md").meta["name"] == "new"
        assert not (ws.root / "p/tasks/old").exists()
        assert list(load(holder).meta["dependencies"]) == ["task:p/new"]
        assert holder in outcome.changed

    def test_archived_task(self, ws):
        ws.project("p")
        ws.task("p", "old", archived=True)
        rename_task(ws.workspace, "p", "old", "new", bases=BASES)
        meta = load(ws.root / "p/.archive/new.md").meta
        assert meta["name"] == "new" and meta["archived"] is not None

    @pytest.mark.parametrize(("new", "match"), [("Bad", "invalid name"), ("taken", "already exists"), ("old", "same as the current name")])
    def test_refusals(self, ws, new, match):
        ws.project("p")
        ws.task("p", "old")
        ws.task("p", "taken", archived=True)
        before = tree(ws.root)
        with pytest.raises(ChreosError, match=match):
            rename_task(ws.workspace, "p", "old", new, bases=BASES)
        assert tree(ws.root) == before

    def test_open_task_refused(self, ws, tmp_path):
        ws.project("p")
        ws.task("p", "old", source={"type": "local", "path": str(tmp_path)})
        open_(ws, "p", "old")
        with pytest.raises(ChreosError, match="close it first"):
            rename_task(ws.workspace, "p", "old", "new", bases=BASES)

    def test_git_branch_is_renamed(self, ws, git_repo):
        ws.project("p")
        ws.task("p", "old", source={"type": "git", "path": str(git_repo)})
        git(git_repo, "branch", "old")
        rename_task(ws.workspace, "p", "old", "new", bases=BASES)
        assert g.branch_exists(git_repo, "new") and not g.branch_exists(git_repo, "old")

    def test_existing_target_branch_refuses(self, ws, git_repo):
        ws.project("p")
        ws.task("p", "old", source={"type": "git", "path": str(git_repo)})
        git(git_repo, "branch", "old")
        git(git_repo, "branch", "new")
        with pytest.raises(ChreosError, match="branch 'new' already exists"):
            rename_task(ws.workspace, "p", "old", "new", bases=BASES)
        assert (ws.root / "p/tasks/old/TASK.md").exists()

    def test_unresolvable_source_warns(self, ws):
        ws.project("p")
        ws.task("p", "old", source={"type": "git", "path": "relative"})
        outcome = rename_task(ws.workspace, "p", "old", "new", bases=BASES)
        assert "branch" in outcome.warnings[0]
        assert (ws.root / "p/tasks/new/TASK.md").exists()

    def test_decision(self, ws):
        ws.project("p")
        ws.decision("p", "old")
        holder = ws.task("p", "h", dependencies=["decision:old"])
        rename_decision(ws.workspace, "p", "old", "new")
        assert load(ws.root / "p/decisions/new.md").meta["name"] == "new"
        assert list(load(holder).meta["dependencies"]) == ["decision:new"]

    def test_project(self, ws, git_repo):
        ws.project("old")
        ws.project("q")
        ws.task("old", "a", source={"type": "git", "path": str(git_repo)})
        ws.task("old", "arch", archived=True)
        ws.decision("old", "d", dependencies=["task:a"])
        holder = ws.task("q", "h", dependencies=["task:old/a", "decision:old/d"])
        open_(ws, "old", "a")
        outcome = rename_project(ws.workspace, "old", "new", default_project="default")
        assert not outcome.renamed_default
        assert ws.workspace.projects() == ["new", "q"]
        for path in ("new/tasks/a/TASK.md", "new/.archive/arch.md", "new/decisions/d.md"):
            assert load(ws.root / path).meta["project"] == "new"
        assert list(load(ws.root / "new/decisions/d.md").meta["dependencies"]) == ["task:a"]
        assert list(load(holder).meta["dependencies"]) == ["task:new/a", "decision:new/d"]
        work = ws.root / "new/tasks/a/work"
        assert g.checked_out_at(git_repo, "a") == work
        assert git(work, "status", "--porcelain") == ""

    def test_project_default_flag_and_refusals(self, ws):
        ws.project("default")
        ws.project("taken")
        assert rename_project(ws.workspace, "default", "inbox", default_project="default").renamed_default
        with pytest.raises(ChreosError, match="already exists"):
            rename_project(ws.workspace, "inbox", "taken", default_project="inbox")
        with pytest.raises(ChreosError, match="does not exist"):
            rename_project(ws.workspace, "nope", "x", default_project="inbox")


class TestDelete:
    def test_task_lists_affected_items_and_removes_references(self, ws, yes):
        ws.project("p")
        ws.project("q")
        ws.task("p", "t")
        holder = ws.task("q", "h", dependencies=["task:p/t", "task:h2"])
        outcome = delete_task(ws.workspace, "p", "t", confirm=yes)
        assert "task:p/t" in yes.messages[0] and "task:q/h" in yes.messages[0]
        assert not (ws.root / "p/tasks/t").exists()
        assert list(load(holder).meta["dependencies"]) == ["task:h2"]
        assert holder in outcome.changed

    def test_refused_confirmation_changes_nothing(self, ws, no):
        ws.project("p")
        ws.task("p", "t")
        holder = ws.task("p", "h", dependencies=["task:t"])
        before = tree(ws.root), holder.read_text()
        with pytest.raises(ChreosError, match="cancelled"):
            delete_task(ws.workspace, "p", "t", confirm=no)
        assert (tree(ws.root), holder.read_text()) == before

    def test_open_git_task_is_cleaned_up_first(self, ws, git_repo):
        ws.project("p")
        ws.task("p", "t", source={"type": "git", "path": str(git_repo)})
        open_(ws, "p", "t")
        delete_task(ws.workspace, "p", "t", confirm=YES)
        assert not (ws.root / "p/tasks/t").exists()
        assert g.checked_out_at(git_repo, "t") is None
        assert g.branch_exists(git_repo, "t")

    def test_archived_task(self, ws):
        ws.project("p")
        ws.task("p", "t", archived=True)
        delete_task(ws.workspace, "p", "t", confirm=YES)
        assert not (ws.root / "p/.archive/t.md").exists()

    def test_decision(self, ws, yes):
        ws.project("p")
        ws.decision("p", "d")
        holder = ws.task("p", "h", dependencies=["decision:d"])
        delete_decision(ws.workspace, "p", "d", confirm=yes)
        assert not (ws.root / "p/decisions/d.md").exists()
        assert list(load(holder).meta["dependencies"]) == []

    def test_project(self, ws, yes):
        ws.project("default")
        ws.project("p")
        ws.task("p", "a")
        ws.task("p", "b", archived=True)
        ws.decision("p", "d")
        holder = ws.task("default", "h", dependencies=["task:p/a", "decision:p/d"])
        delete_project(ws.workspace, "p", default_project="default", confirm=yes)
        message = yes.messages[0]
        assert "2 tasks" in message and "1 decision" in message and "task:default/h" in message
        assert ws.workspace.projects() == ["default"]
        assert list(load(holder).meta["dependencies"]) == []

    def test_default_project_protected(self, ws):
        ws.project("default")
        with pytest.raises(ChreosError, match="default project"):
            delete_project(ws.workspace, "default", default_project="default", confirm=YES)


class TestMove:
    def test_live_task(self, ws):
        for p in ("src", "dest"):
            ws.project(p)
        ws.task("src", "t", dependencies=["task:sibling"])
        ws.task("src", "sibling")
        from_src = ws.task("src", "h", dependencies=["task:t"])
        outcome = move_task(ws.workspace, "src", "t", "dest")
        moved = ws.root / "dest/tasks/t/TASK.md"
        meta = load(moved).meta
        assert meta["project"] == "dest"
        assert list(meta["dependencies"]) == ["task:src/sibling"]
        assert list(load(from_src).meta["dependencies"]) == ["task:dest/t"]
        assert moved in outcome.changed

    def test_archived_task_stays_archived(self, ws):
        ws.project("src")
        ws.project("dest")
        ws.task("src", "t", archived=True)
        move_task(ws.workspace, "src", "t", "dest")
        assert load(ws.root / "dest/.archive/t.md").meta["archived"] is not None

    def test_refusals(self, ws, tmp_path):
        ws.project("src")
        ws.project("dest")
        ws.task("src", "t", source={"type": "local", "path": str(tmp_path)})
        ws.task("dest", "clash", archived=True)
        ws.task("src", "clash")
        with pytest.raises(ChreosError, match="does not exist"):
            move_task(ws.workspace, "src", "t", "nowhere")
        with pytest.raises(ChreosError, match="already in"):
            move_task(ws.workspace, "src", "t", "src")
        with pytest.raises(ChreosError, match="already exists"):
            move_task(ws.workspace, "src", "clash", "dest")
        open_(ws, "src", "t")
        with pytest.raises(ChreosError, match="close it first"):
            move_task(ws.workspace, "src", "t", "dest")

    def test_decision(self, ws):
        ws.project("src")
        ws.project("dest")
        ws.decision("src", "d", dependencies=["task:dest/x"])
        holder = ws.task("dest", "h", dependencies=["decision:src/d"])
        move_decision(ws.workspace, "src", "d", "dest")
        moved = ws.root / "dest/decisions/d.md"
        assert load(moved).meta["project"] == "dest"
        assert list(load(moved).meta["dependencies"]) == ["task:x"]
        assert list(load(holder).meta["dependencies"]) == ["decision:d"]
