import shutil

from chreos.frontmatter import load
from chreos.graph import Node
from chreos.model import Kind
from chreos.relink import rewrite, snapshot


def task(project, name):
    return Node(Kind.TASK, project, name)


def decision(project, name):
    return Node(Kind.DECISION, project, name)


def with_refs(path, *refs):
    text = path.read_text().replace("## References\n", "## References\n\n" + "".join(f"- {r}\n" for r in refs))
    path.write_text(text)


def deps(path):
    return list(load(path).meta["dependencies"])


def refs(path):
    from chreos.lists import ListKind, read_items

    return [item.text for item in read_items(load(path).body, "References", ListKind.BULLETS)]


def test_snapshot_lists_every_task_and_decision(ws):
    ws.project("p")
    live = ws.task("p", "live")
    old = ws.task("p", "old", archived=True)
    dec = ws.decision("p", "d")
    assert snapshot(ws.workspace) == [(task("p", "live"), live), (task("p", "old"), old), (decision("p", "d"), dec)]


def test_rename_task_rewrites_local_and_cross_project_refs(ws):
    ws.project("p")
    ws.project("q")
    ws.task("p", "old-name")
    local = ws.task("p", "local", dependencies=["task:old-name", "decision:old-name"])
    with_refs(local, "task:old-name", "[link](https://x.example)")
    remote = ws.task("q", "remote", dependencies=["task:p/old-name"])
    untouched = ws.decision("q", "d", dependencies=["task:remote"])
    before = untouched.read_text()
    snap = snapshot(ws.workspace)
    src = ws.root / "p/tasks/old-name"
    src.rename(ws.root / "p/tasks/new-name")
    report = rewrite(ws.workspace, snap, {task("p", "old-name"): task("p", "new-name")})
    assert deps(local) == ["task:new-name", "decision:old-name"]
    assert refs(local) == ["task:new-name", "[link](https://x.example)"]
    assert deps(remote) == ["task:p/new-name"]
    assert untouched.read_text() == before
    assert sorted(report.changed) == sorted([local, remote])


def test_move_rewrites_both_directions(ws):
    for p in ("src", "dest", "third"):
        ws.project(p)
    ws.task("src", "sibling")
    ws.task("dest", "target")
    ws.task("src", "mover", dependencies=["task:sibling", "task:dest/target", "task:third/x"])
    from_src = ws.task("src", "from-src", dependencies=["task:mover"])
    from_dest = ws.task("dest", "from-dest", dependencies=["task:src/mover"])
    from_third = ws.decision("third", "from-third", dependencies=["task:src/mover"])
    snap = snapshot(ws.workspace)
    shutil.move(ws.root / "src/tasks/mover", ws.root / "dest/tasks/mover")
    rewrite(ws.workspace, snap, {task("src", "mover"): task("dest", "mover")})
    moved = ws.root / "dest/tasks/mover/TASK.md"
    assert deps(moved) == ["task:src/sibling", "task:target", "task:third/x"]
    assert deps(from_src) == ["task:dest/mover"]
    assert deps(from_dest) == ["task:mover"]
    assert deps(from_third) == ["task:dest/mover"]


def test_project_rename(ws):
    ws.project("old")
    ws.project("q")
    inside = ws.task("old", "a", dependencies=["task:b", "decision:q/d"])
    ws.task("old", "b")
    ws.decision("q", "d", dependencies=["task:old/a"])
    snap = snapshot(ws.workspace)
    (ws.root / "old").rename(ws.root / "new")
    node_map = {node: Node(node.kind, "new", node.name) for node, _ in snap if node.project == "old"}
    rewrite(ws.workspace, snap, node_map)
    assert deps(ws.root / "new/tasks/a/TASK.md") == ["task:b", "decision:q/d"]
    assert deps(ws.root / "q/decisions/d.md") == ["task:new/a"]
    assert not inside.exists()


def test_delete_removes_entries(ws):
    ws.project("p")
    gone = ws.decision("p", "gone")
    holder = ws.task("p", "h", dependencies=["decision:gone", "task:other"])
    with_refs(holder, "decision:gone", "https://keep.example")
    ws.task("p", "other")
    snap = snapshot(ws.workspace)
    gone.unlink()
    rewrite(ws.workspace, snap, {decision("p", "gone"): None})
    assert deps(holder) == ["task:other"]
    assert refs(holder) == ["https://keep.example"]


def test_explicit_own_project_prefix_is_kept_when_nothing_changes(ws):
    ws.project("p")
    ws.task("p", "a")
    holder = ws.task("p", "h", dependencies=["task:p/a"])
    before = holder.read_text()
    snap = snapshot(ws.workspace)
    report = rewrite(ws.workspace, snap, {task("p", "zzz"): None})
    assert holder.read_text() == before
    assert report.changed == []


def test_comments_in_dependencies_and_updated_bump(ws):
    ws.project("p")
    ws.task("p", "old")
    holder = ws.task("p", "h")
    text = holder.read_text().replace("dependencies: []", "dependencies:\n  - task:old  # important\n  - task:x")
    holder.write_text(text)
    before = load(holder).meta["updated"]
    snap = snapshot(ws.workspace)
    (ws.root / "p/tasks/old").rename(ws.root / "p/tasks/new")
    rewrite(ws.workspace, snap, {task("p", "old"): task("p", "new")})
    assert "  - task:new  # important\n  - task:x\n" in holder.read_text()
    assert load(holder).meta["updated"] >= before


def test_broken_files_are_skipped(ws):
    ws.project("p")
    ws.task("p", "old")
    broken = ws.write("p/tasks/broken/TASK.md", "no frontmatter")
    snap = snapshot(ws.workspace)
    (ws.root / "p/tasks/old").rename(ws.root / "p/tasks/new")
    report = rewrite(ws.workspace, snap, {task("p", "old"): task("p", "new")})
    assert [failure.path for failure in report.skipped] == [broken]
