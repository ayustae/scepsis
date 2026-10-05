"""`chreos check`: validate the whole workspace (design §12.1, §11.5).

Errors are things that are wrong (invalid data, broken links between items,
broken lifecycle state); warnings are worth attention but tolerated.
"""

from dataclasses import dataclass
from pathlib import Path

from chreos import git
from chreos.editing import expected_caches, file_checks
from chreos.errors import ChreosError, FormatError
from chreos.frontmatter import Document, load, save
from chreos.graph import Graph, Node
from chreos.lists import ListKind, read_items
from chreos.model import Kind, Phase, TaskStatus, is_valid_name
from chreos.refs import validate_reference
from chreos.sources import Bases, Source, source_warnings
from chreos.timestamps import now
from chreos.workspace import ARCHIVE, DECISIONS, PROJECT_FILE, TASK_FILE, TASKS, Workspace

ERROR, WARNING = "error", "warning"


@dataclass(frozen=True)
class Finding:
    severity: str
    path: Path
    item: str | None
    message: str


@dataclass(frozen=True)
class _Item:
    kind: Kind
    project: str
    name: str
    path: Path
    archived: bool = False

    @property
    def label(self) -> str:
        return f"project:{self.name}" if self.kind is Kind.PROJECT else f"{self.kind}:{self.project}/{self.name}"


def _entries(folder: Path) -> list[Path]:
    return sorted(folder.iterdir()) if folder.is_dir() else []


def _layout(workspace: Workspace, found: list[Finding]) -> list[_Item]:
    """Collect every item file and report entries that don't belong to the layout (§2)."""
    items = []

    def stray(path: Path, what: str) -> None:
        found.append(Finding(WARNING, path, None, f"{what}; chreos ignores it"))

    for entry in _entries(workspace.root):
        if entry.name.startswith("."):
            continue
        if not (entry.is_dir() and is_valid_name(entry.name) and (entry / PROJECT_FILE).is_file()):
            stray(entry, "not a project (projects are folders with a PROJECT.md and a valid name)")
            continue
        project = entry.name
        items.append(_Item(Kind.PROJECT, project, project, entry / PROJECT_FILE))
        for task in _entries(entry / TASKS):
            if task.is_dir() and is_valid_name(task.name) and (task / TASK_FILE).is_file():
                items.append(_Item(Kind.TASK, project, task.name, task / TASK_FILE))
            else:
                stray(task, "not a task (tasks are folders with a TASK.md and a valid name)")
        for kind, folder, archived in ((Kind.TASK, ARCHIVE, True), (Kind.DECISION, DECISIONS, False)):
            for file in _entries(entry / folder):
                if file.is_file() and file.suffix == ".md" and is_valid_name(file.stem):
                    items.append(_Item(kind, project, file.stem, file, archived))
                else:
                    stray(file, f"not a {'archived task' if archived else 'decision'} (expected <name>.md)")
    return items


def _lifecycle(item: _Item, doc: Document, graph: Graph, bases: Bases) -> list[Finding]:
    found = []

    def add(severity, message):
        found.append(Finding(severity, item.path, item.label, message))

    meta, task_dir = doc.meta, item.path.parent
    if meta.get("phase") == Phase.OPEN:
        work = task_dir / "work"
        working = (work.is_symlink() and work.exists()) or (
            work.is_dir() and not work.is_symlink() and git.is_worktree(work)
        )
        if not working:
            state = "has no work/" if not (work.exists() or work.is_symlink()) else "has a broken work/"
            add(ERROR, f"the open task {state}; 'chreos task open --recreate' rebuilds it")
    else:
        leftovers = sorted(e.name for e in task_dir.iterdir() if e.name != TASK_FILE)
        if leftovers:
            add(WARNING, f"the closed task folder contains {', '.join(leftovers)}; 'chreos task close' cleans it up")

    node = Node(Kind.TASK, item.project, item.name)
    statuses = graph.dependency_statuses(node) if node in graph else []
    status = meta.get("status")
    if status == TaskStatus.ON_HOLD and statuses and all(s.satisfied for s in statuses):
        add(WARNING, "the task is on-hold but all its dependencies are satisfied")
    if status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS) and not all(s.satisfied for s in statuses):
        add(WARNING, f"the task is {status} but has unsatisfied dependencies")
    try:
        source = Source.from_meta(meta.get("source"))
    except ChreosError:
        source = None  # reported by the schema check
    if source is not None:
        for problem in source_warnings(source, bases):
            add(WARNING, f"source: {problem}")
    return found


def check_workspace(workspace: Workspace, bases: Bases) -> list[Finding]:
    found: list[Finding] = []
    items = _layout(workspace, found)
    graph = Graph.load(workspace)
    live_tasks = {(i.project, i.name) for i in items if i.kind is Kind.TASK and not i.archived}

    for item in items:
        def add(severity, message, item=item):
            found.append(Finding(severity, item.path, item.label, message))

        if item.archived and (item.project, item.name) in live_tasks:
            add(ERROR, "the task is both live and archived; rename or delete one of them")
        try:
            doc = load(item.path)
        except (FormatError, OSError) as error:
            add(ERROR, str(error).removeprefix(f"{item.path}: "))
            continue
        errors, warnings = file_checks(item.path, item.kind, doc)
        for message in errors:
            add(ERROR, message)
        for message in warnings:
            add(WARNING, message)
        if item.kind is not Kind.TASK:
            continue
        if item.archived and doc.meta.get("archived") is None:
            add(ERROR, "the archived task has no 'archived' timestamp")
        if not item.archived and "archived" in doc.meta:
            add(ERROR, "the live task has an 'archived' timestamp; remove it or archive the task")
        if not item.archived:
            found.extend(_lifecycle(item, doc, graph, bases))
        for entry in read_items(doc.body, "References", ListKind.BULLETS):
            try:
                validate_reference(workspace, item.project, entry.text)
            except ChreosError as error:
                add(WARNING, f"## References: {error}")

    paths: dict[tuple, Path] = {}
    for item in items:  # live tasks come before archived ones, so a clash points at the live file
        paths.setdefault((item.kind, item.project, item.name), item.path)
    for problem in graph.problems:
        node = problem.node
        found.append(Finding(ERROR, paths.get((node.kind, node.project, node.name), workspace.root), str(node), problem.message))
    for cycle in graph.find_cycles():
        first = cycle[0]
        found.append(Finding(
            ERROR, paths.get((first.kind, first.project, first.name), workspace.root), str(first),
            f"dependency cycle: {' -> '.join(str(n) for n in cycle)}",
        ))
    return sorted(found, key=lambda f: (str(f.path), f.message))


def fix_caches(workspace: Workspace) -> list[Path]:
    """Rewrite drifted `name`/`project` caches to match the paths; touch nothing else (§4)."""
    fixed = []
    for item in _layout(workspace, []):
        try:
            doc = load(item.path)
        except (FormatError, OSError):
            continue
        changed = False
        for key, expected in expected_caches(item.path, item.kind).items():
            if doc.meta.get(key) != expected:
                doc.meta[key] = expected
                changed = True
        if changed:
            doc.meta["updated"] = now()
            save(item.path, doc)
            fixed.append(item.path)
    return fixed
