import pytest

from chreos.check import check_workspace, fix_caches
from chreos.frontmatter import load
from chreos.model import SourceType

BASES = {SourceType.GIT: None, SourceType.LOCAL: None}


def findings(ws):
    return check_workspace(ws.workspace, BASES)


def find(ws, needle, severity=None):
    """The findings whose message contains `needle`."""
    found = [f for f in findings(ws) if needle in f.message]
    if severity:
        assert all(f.severity == severity for f in found), found
    return found


@pytest.fixture
def p(ws):
    ws.project("p")
    return ws


def test_clean_workspace(p):
    p.task("p", "a")
    p.task("p", "b", dependencies=["task:a"], status="done")
    p.task("p", "old", archived=True)
    p.decision("p", "d", dependencies=["task:a"])
    assert findings(p) == []


class TestLayout:
    def test_stray_entries(self, p):
        p.write("notes/readme.md", "x")  # folder without PROJECT.md
        p.write(".hidden/x", "x")  # ignored
        p.write("p/tasks/stray.md", "x")
        p.write("p/tasks/no-file/notes.md", "x")
        p.write("p/.archive/Bad.md", "x")
        p.write("p/.archive/folder/x.md", "x")
        p.write("p/decisions/readme.txt", "x")
        messages = [(f.severity, str(f.path.relative_to(p.root))) for f in findings(p)]
        assert ("warning", "notes") in messages
        for path in ("p/tasks/stray.md", "p/tasks/no-file", "p/.archive/Bad.md", "p/.archive/folder", "p/decisions/readme.txt"):
            assert ("warning", path) in messages
        assert not any(".hidden" in path for _, path in messages)


class TestFiles:
    def test_unparseable(self, p):
        p.write("p/tasks/broken/TASK.md", "no frontmatter")
        found = find(p, "no frontmatter", "error")
        assert len(found) == 1 and found[0].item == "task:p/broken"

    def test_schema_and_caches(self, p):
        path = p.task("p", "t")
        path.write_text(path.read_text().replace("status: new", "status: bogus").replace("name: t", "name: other"))
        assert find(p, "status", "error")
        assert find(p, "doesn't match the path", "error")

    def test_body_warning(self, p):
        path = p.decision("p", "d")
        path.write_text(path.read_text().replace("# d", "# Something else"))
        assert find(p, "H1", "warning")


class TestArchiveAndUniqueness:
    def test_live_and_archived_clash(self, p):
        p.task("p", "t")
        p.write("p/.archive/t.md", (p.root / "p/tasks/t/TASK.md").read_text())
        assert find(p, "both live and archived", "error")

    def test_archived_field_mismatch(self, p):
        archived = p.task("p", "old", archived=True)
        archived.write_text("\n".join(l for l in archived.read_text().splitlines() if not l.startswith("archived:")) + "\n")
        live = p.task("p", "live")
        live.write_text(live.read_text().replace("labels: []", "labels: []\narchived: 2026-01-01T00:00:00+00:00"))
        assert len(find(p, "archived", "error")) == 2


class TestDependencies:
    def test_unresolved_and_cycles(self, p):
        p.task("p", "a", dependencies=["task:b", "task:gone"])
        p.task("p", "b", dependencies=["task:a"])
        assert find(p, "task:gone", "error")
        cycles = find(p, "cycle", "error")
        assert len(cycles) == 1 and "task:p/a" in cycles[0].message and "task:p/b" in cycles[0].message


class TestLifecycle:
    def test_open_task_without_work(self, p, tmp_path):
        p.task("p", "t", phase="open", status="todo", source={"type": "local", "path": str(tmp_path)})
        found = find(p, "work/", "error")
        assert found and "--recreate" in found[0].message

    def test_broken_link(self, p, tmp_path):
        path = p.task("p", "t", phase="open", status="todo", source={"type": "local", "path": str(tmp_path)})
        (path.parent / "work").symlink_to(tmp_path / "gone")
        assert find(p, "work/", "error")

    def test_valid_open_task(self, p, tmp_path):
        path = p.task("p", "t", phase="open", status="todo", source={"type": "local", "path": str(tmp_path)})
        (path.parent / "work").symlink_to(tmp_path)
        assert findings(p) == []

    def test_closed_task_with_leftovers(self, p):
        path = p.task("p", "t")
        (path.parent / "leftover.txt").write_text("x")
        found = find(p, "leftover.txt", "warning")
        assert found and "task close" in found[0].message

    def test_status_vs_dependencies(self, p, tmp_path):
        p.task("p", "done-dep", status="done")
        p.task("p", "open-dep")
        for name, status, dep in (("held", "on-hold", "task:done-dep"), ("eager", "in-progress", "task:open-dep")):
            path = p.task("p", name, phase="open", status=status, dependencies=[dep], source={"type": "local", "path": str(tmp_path)})
            (path.parent / "work").symlink_to(tmp_path)
        assert find(p, "on-hold but all its dependencies are satisfied", "warning")
        assert find(p, "in-progress but has unsatisfied dependencies", "warning")

    def test_unresolvable_source(self, p):
        p.task("p", "t", source={"type": "git", "path": "relative"})
        assert find(p, "source.git_path", "warning")


def test_unresolved_reference_in_section(p):
    path = p.task("p", "t")
    path.write_text(path.read_text().replace("## References\n", "## References\n\n- decision:nope\n- https://ok.example\n"))
    found = find(p, "decision:nope", "warning")
    assert len(found) == 1


def test_fix_caches_only(p):
    path = p.task("p", "t")
    path.write_text(path.read_text().replace("name: t", "name: stale").replace("project: p", "project: q").replace("status: new", "status: bogus"))
    decision = p.decision("p", "d")
    before = decision.read_text()
    fixed = fix_caches(p.workspace)
    assert fixed == [path]
    meta = load(path).meta
    assert (meta["name"], meta["project"], meta["status"]) == ("t", "p", "bogus")
    assert decision.read_text() == before
    assert not find(p, "doesn't match the path")
    assert find(p, "status", "error")
