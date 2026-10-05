"""Archive, restore, rename, delete and move (design §7).

Each operation validates and asks for confirmation first, then changes the
filesystem, then rewrites references (`relink`). Callers hold the workspace
lock. Operations span several files and are not transactional: if one is
interrupted, `chreos check` reports what was left inconsistent.
"""

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from chreos import git
from chreos.confirmations import Confirm, require
from chreos.errors import ChreosError
from chreos.frontmatter import Document, load, save
from chreos.graph import Graph, Node
from chreos.lifecycle import cleanup, close_task
from chreos.model import Kind, Phase, SourceType, validate_name
from chreos.relink import NodeMap, referrers, rewrite, snapshot
from chreos.sources import Bases, Source, resolve
from chreos.timestamps import now
from chreos.workspace import Workspace


@dataclass
class Outcome:
    changed: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    renamed_default: bool = False


def _always(_: str) -> bool:
    return True


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _require_project(workspace: Workspace, project: str) -> None:
    if not workspace.project_exists(project):
        raise ChreosError(f"project '{project}' does not exist")


def _locate_task(workspace: Workspace, project: str, name: str) -> tuple[Path, bool]:
    _require_project(workspace, project)
    live = workspace.live_task_file(project, name)
    if live.is_file():
        return live, False
    archived = workspace.archived_task_file(project, name)
    if archived.is_file():
        return archived, True
    raise ChreosError(f"task '{project}/{name}' does not exist")


def _locate_decision(workspace: Workspace, project: str, name: str) -> Path:
    _require_project(workspace, project)
    path = workspace.decision_file(project, name)
    if not path.is_file():
        raise ChreosError(f"decision '{project}/{name}' does not exist")
    return path


def _refuse_open(doc: Document, project: str, name: str, action: str) -> None:
    if doc.meta.get("phase") == Phase.OPEN:
        raise ChreosError(f"task '{project}/{name}' is open and cannot be {action}; close it first")


def _save_with(path: Path, doc: Document, **fields) -> None:
    for key, value in fields.items():
        doc.meta[key] = value
    doc.meta["updated"] = now()
    save(path, doc)


def _finish(workspace: Workspace, before, node_map: NodeMap, outcome: Outcome) -> Outcome:
    report = rewrite(workspace, before, node_map)
    outcome.changed.extend(path for path in report.changed if path not in outcome.changed)
    outcome.warnings.extend(f"references not updated in {f.message}" for f in report.skipped)
    return outcome


def _new_name(workspace: Workspace, kind: Kind, project: str | None, name: str, new_name: str) -> None:
    validate_name(new_name)
    if new_name == name:
        raise ChreosError(f"the new name is the same as the current name '{name}'")
    workspace.ensure_free(kind, project, new_name)


# Archive and restore


def archive_task(
    workspace: Workspace,
    graph: Graph,
    project: str,
    name: str,
    *,
    confirm: Confirm,
    force: bool = False,
    status: str | None = None,
) -> Outcome:
    path, archived = _locate_task(workspace, project, name)
    if archived:
        raise ChreosError(f"task '{project}/{name}' is already archived")
    target = workspace.archived_task_file(project, name)
    if target.exists():
        raise ChreosError(f"{target} already exists; run 'chreos check'")
    if load(path).meta.get("phase") == Phase.OPEN:
        if not force:
            raise ChreosError(
                f"task '{project}/{name}' is open; close it first (or use -f to close and archive)"
            )
        close_task(workspace, graph, project, name, confirm=_always, status=status)
    else:
        cleanup(path.parent, confirm)
    doc = load(path)
    workspace.ensure_project_dirs(project)
    _save_with(target, doc, archived=now())
    path.unlink()
    path.parent.rmdir()
    return Outcome(changed=[target])


def restore_task(workspace: Workspace, project: str, name: str) -> Outcome:
    _require_project(workspace, project)
    path = workspace.archived_task_file(project, name)
    live = workspace.live_task_file(project, name)
    if not path.is_file():
        if live.is_file():
            raise ChreosError(f"task '{project}/{name}' is not archived")
        raise ChreosError(f"task '{project}/{name}' does not exist")
    if live.exists() or live.parent.exists():
        raise ChreosError(f"a live task '{project}/{name}' already exists; run 'chreos check'")
    doc = load(path)
    doc.meta.pop("archived", None)
    live.parent.mkdir(parents=True)
    _save_with(live, doc)
    path.unlink()
    return Outcome(changed=[live])


# Rename


def _rename_branch(doc: Document, name: str, new_name: str, bases: Bases) -> list[str]:
    try:
        source = Source.from_meta(doc.meta.get("source"))
        if source is None or source.type is not SourceType.GIT:
            return []
        repo = git.toplevel(resolve(source, bases))
    except ChreosError as error:
        return [f"the git branch '{name}' was not renamed: {error}"]
    if not git.branch_exists(repo, name):
        return []
    if git.branch_exists(repo, new_name):
        raise ChreosError(f"branch '{new_name}' already exists in {repo}")
    git.rename_branch(repo, name, new_name)
    return []


def rename_task(workspace: Workspace, project: str, name: str, new_name: str, *, bases: Bases) -> Outcome:
    path, archived = _locate_task(workspace, project, name)
    _new_name(workspace, Kind.TASK, project, name, new_name)
    doc = load(path)
    _refuse_open(doc, project, name, "renamed")
    warnings = _rename_branch(doc, name, new_name, bases)
    before = snapshot(workspace)
    if archived:
        new_path = workspace.archived_task_file(project, new_name)
        path.rename(new_path)
    else:
        path.parent.rename(workspace.tasks_dir(project) / new_name)
        new_path = workspace.live_task_file(project, new_name)
    _save_with(new_path, doc, name=new_name)
    node_map = {Node(Kind.TASK, project, name): Node(Kind.TASK, project, new_name)}
    return _finish(workspace, before, node_map, Outcome([new_path], warnings))


def rename_decision(workspace: Workspace, project: str, name: str, new_name: str) -> Outcome:
    path = _locate_decision(workspace, project, name)
    _new_name(workspace, Kind.DECISION, project, name, new_name)
    doc = load(path)
    before = snapshot(workspace)
    new_path = workspace.decision_file(project, new_name)
    path.rename(new_path)
    _save_with(new_path, doc, name=new_name)
    node_map = {Node(Kind.DECISION, project, name): Node(Kind.DECISION, project, new_name)}
    return _finish(workspace, before, node_map, Outcome([new_path]))


def _items_of(workspace: Workspace, project: str) -> list[Path]:
    return [path for node, path in snapshot(workspace) if node.project == project]


def rename_project(workspace: Workspace, name: str, new_name: str, *, default_project: str) -> Outcome:
    _require_project(workspace, name)
    _new_name(workspace, Kind.PROJECT, None, name, new_name)
    before = snapshot(workspace)
    worktrees = [
        task
        for task in workspace.task_names(name)
        if (work := workspace.tasks_dir(name) / task / "work").is_dir()
        and not work.is_symlink()
        and (work / ".git").exists()
    ]
    workspace.project_dir(name).rename(workspace.project_dir(new_name))
    outcome = Outcome(renamed_default=name == default_project)
    project_doc = load(workspace.project_file(new_name))
    _save_with(workspace.project_file(new_name), project_doc, name=new_name)
    outcome.changed.append(workspace.project_file(new_name))
    for path in _items_of(workspace, new_name):
        _save_with(path, load(path), project=new_name)
        outcome.changed.append(path)
    for task in worktrees:
        try:
            git.worktree_repair(workspace.tasks_dir(new_name) / task / "work")
        except ChreosError as error:
            outcome.warnings.append(f"could not repair the worktree of task '{new_name}/{task}': {error}")
    node_map = {
        node: Node(node.kind, new_name, node.name) for node, _ in before if node.project == name
    }
    return _finish(workspace, before, node_map, outcome)


# Delete


def _confirm_delete(workspace: Workspace, what: str, targets: set[Node], confirm: Confirm) -> None:
    affected = [str(node) for node in referrers(workspace, targets) if node not in targets]
    message = f"Permanently delete {what}?"
    if affected:
        message += f"\nReferences to it will be removed from: {', '.join(affected)}"
    require(message, confirm)


def delete_task(workspace: Workspace, project: str, name: str, *, confirm: Confirm) -> Outcome:
    path, archived = _locate_task(workspace, project, name)
    node = Node(Kind.TASK, project, name)
    _confirm_delete(workspace, str(node), {node}, confirm)
    before = snapshot(workspace)
    if archived:
        path.unlink()
    else:
        cleanup(path.parent, confirm)
        shutil.rmtree(path.parent)
    return _finish(workspace, before, {node: None}, Outcome())


def delete_decision(workspace: Workspace, project: str, name: str, *, confirm: Confirm) -> Outcome:
    path = _locate_decision(workspace, project, name)
    node = Node(Kind.DECISION, project, name)
    _confirm_delete(workspace, str(node), {node}, confirm)
    before = snapshot(workspace)
    path.unlink()
    return _finish(workspace, before, {node: None}, Outcome())


def delete_project(workspace: Workspace, name: str, *, default_project: str, confirm: Confirm) -> Outcome:
    _require_project(workspace, name)
    if name == default_project:
        raise ChreosError("the default project cannot be deleted")
    before = snapshot(workspace)
    nodes = {node for node, _ in before if node.project == name}
    tasks = sum(1 for node in nodes if node.kind is Kind.TASK)
    what = f"project '{name}' with {_plural(tasks, 'task')} and {_plural(len(nodes) - tasks, 'decision')}"
    _confirm_delete(workspace, what, nodes, confirm)
    for task in workspace.task_names(name):
        cleanup(workspace.tasks_dir(name) / task, confirm)
    shutil.rmtree(workspace.project_dir(name))
    return _finish(workspace, before, dict.fromkeys(nodes), Outcome())


# Move


def _check_destination(workspace: Workspace, kind: Kind, project: str, name: str, dest: str) -> None:
    _require_project(workspace, dest)
    if dest == project:
        raise ChreosError(f"{kind} '{project}/{name}' is already in project '{dest}'")
    workspace.ensure_free(kind, dest, name)


def move_task(workspace: Workspace, project: str, name: str, dest: str) -> Outcome:
    path, archived = _locate_task(workspace, project, name)
    _check_destination(workspace, Kind.TASK, project, name, dest)
    doc = load(path)
    _refuse_open(doc, project, name, "moved")
    before = snapshot(workspace)
    workspace.ensure_project_dirs(dest)
    if archived:
        new_path = workspace.archived_task_file(dest, name)
        path.rename(new_path)
    else:
        path.parent.rename(workspace.tasks_dir(dest) / name)
        new_path = workspace.live_task_file(dest, name)
    _save_with(new_path, doc, project=dest)
    node_map = {Node(Kind.TASK, project, name): Node(Kind.TASK, dest, name)}
    return _finish(workspace, before, node_map, Outcome([new_path]))


def move_decision(workspace: Workspace, project: str, name: str, dest: str) -> Outcome:
    path = _locate_decision(workspace, project, name)
    _check_destination(workspace, Kind.DECISION, project, name, dest)
    doc = load(path)
    before = snapshot(workspace)
    workspace.ensure_project_dirs(dest)
    new_path = workspace.decision_file(dest, name)
    path.rename(new_path)
    _save_with(new_path, doc, project=dest)
    node_map = {Node(Kind.DECISION, project, name): Node(Kind.DECISION, dest, name)}
    return _finish(workspace, before, node_map, Outcome([new_path]))
