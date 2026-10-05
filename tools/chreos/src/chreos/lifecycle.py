"""Task lifecycle: open, close and the cleanup of task folders (design §11).

All validation and confirmations happen before anything is removed or
written, and TASK.md is saved last, so a failure leaves the frontmatter
unchanged. Callers hold the workspace lock.
"""

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from chreos import git
from chreos.confirmations import Confirm, done_message, require
from chreos.errors import ChreosError
from chreos.frontmatter import Document, load, save
from chreos.graph import Graph
from chreos.model import Phase, SourceType, TaskStatus, check_status_for_phase
from chreos.sources import Bases, Source, require_source
from chreos.tasks import set_assignee
from chreos.timestamps import now
from chreos.workspace import TASK_FILE, Workspace

WORK = "work"
CLOSING_STATUSES = {TaskStatus.DONE, TaskStatus.CANCELLED}


@dataclass
class Outcome:
    doc: Document
    warnings: list[str] = field(default_factory=list)


# Task folder cleanup


def _work_present(work: Path) -> bool:
    return work.exists() or work.is_symlink()


def losses(task_dir: Path, only_work: bool = False) -> list[str]:
    """What a cleanup would destroy: uncommitted work and files besides TASK.md."""
    found = []
    for entry in sorted(task_dir.iterdir()):
        if entry.name == TASK_FILE or (only_work and entry.name != WORK):
            continue
        if entry.name == WORK and not entry.is_symlink():
            if git.is_worktree(entry):
                found.extend(f"{WORK}/: {line}" for line in git.dirty_files(entry))
            else:
                found.append(f"{WORK}/ (not a git worktree or link)")
        elif entry.name != WORK:
            found.append(f"{entry.name}/" if entry.is_dir() and not entry.is_symlink() else entry.name)
    return found


def cleanup(task_dir: Path, confirm: Confirm, only_work: bool = False) -> None:
    """Remove everything but TASK.md (or only `work/`), asking first if anything would be lost."""
    found = losses(task_dir, only_work)
    if found:
        listing = "\n".join(f"  - {item}" for item in found)
        require(f"This will permanently delete:\n{listing}\nContinue?", confirm)
    work = task_dir / WORK
    if not work.is_symlink() and work.is_dir() and git.is_worktree(work):
        git.worktree_remove(work, force=bool(found))  # the branch is kept
    for entry in task_dir.iterdir():
        if entry.name == TASK_FILE or (only_work and entry.name != WORK):
            continue
        if entry.is_symlink() or not entry.is_dir():
            entry.unlink()  # a link is removed, its target never entered
        else:
            shutil.rmtree(entry)


def create_work(
    task_dir: Path, name: str, source: Source, resolved: Path, repo: Path | None, base: str | None
) -> None:
    work = task_dir / WORK
    if source.type is SourceType.LOCAL:
        work.symlink_to(resolved, target_is_directory=True)
        return
    git.worktree_prune(repo)
    elsewhere = git.checked_out_at(repo, name)
    if elsewhere is not None:
        raise ChreosError(
            f"branch '{name}' is already checked out at {elsewhere}; "
            "remove that worktree or rename one of the tasks"
        )
    git.worktree_add(repo, work, name, base or git.default_base(repo))


# Open and close


def _load_live_task(workspace: Workspace, project: str, name: str) -> tuple[Path, Document]:
    path = workspace.live_task_file(project, name)
    if not path.is_file():
        if workspace.archived_task_file(project, name).is_file():
            raise ChreosError(f"task '{project}/{name}' is archived; restore it first")
        raise ChreosError(f"task '{project}/{name}' does not exist")
    return path, load(path)


def _parse_status(status: str | None) -> TaskStatus | None:
    if status is None:
        return None
    try:
        return TaskStatus(status)
    except ValueError:
        raise ChreosError(f"invalid task status {status!r}") from None


def _save(path: Path, doc: Document, phase: Phase, status: TaskStatus) -> None:
    doc.meta["phase"] = phase
    doc.meta["status"] = status
    doc.meta["updated"] = now()
    save(path, doc)


def open_task(
    workspace: Workspace,
    graph: Graph,
    project: str,
    name: str,
    *,
    bases: Bases,
    confirm: Confirm,
    status: str | None = None,
    recreate: bool = False,
    base: str | None = None,
    assignee: str | None = None,
) -> Outcome:
    path, doc = _load_live_task(workspace, project, name)
    meta, task_dir = doc.meta, path.parent
    if assignee is not None:
        set_assignee(meta, assignee, confirm)  # asked before anything changes
    requested = _parse_status(status)
    if requested is not None:
        check_status_for_phase(Phase.OPEN, requested)
    statuses = graph.statuses_for(project, list(meta.get("dependencies") or []))
    if requested is TaskStatus.DONE:
        require(done_message(doc.body, statuses), confirm)

    work = task_dir / WORK
    if meta.get("phase") == Phase.OPEN:
        if recreate or not _work_present(work):
            source, resolved, repo = require_source(meta, bases)
            if _work_present(work):
                cleanup(task_dir, confirm, only_work=True)
            create_work(task_dir, name, source, resolved, repo, base)
        new_status = requested or TaskStatus(meta["status"])
    else:
        source, resolved, repo = require_source(meta, bases)
        cleanup(task_dir, confirm)  # a closed task folder should hold only TASK.md
        create_work(task_dir, name, source, resolved, repo, base)
        satisfied = all(status.satisfied for status in statuses)
        new_status = requested or (TaskStatus.TODO if satisfied else TaskStatus.ON_HOLD)

    _save(path, doc, Phase.OPEN, new_status)
    return Outcome(doc)


def close_task(
    workspace: Workspace,
    graph: Graph,
    project: str,
    name: str,
    *,
    confirm: Confirm,
    status: str | None = None,
) -> Outcome:
    path, doc = _load_live_task(workspace, project, name)
    meta, task_dir = doc.meta, path.parent
    if meta.get("phase") != Phase.OPEN:
        cleanup(task_dir, confirm)
        warnings = ["--status ignored: the task is already closed"] if status else []
        return Outcome(doc, warnings)

    requested = _parse_status(status)
    if requested is not None and requested not in CLOSING_STATUSES:
        raise ChreosError("a task can only be closed as done or cancelled")
    new_status = requested or TaskStatus(meta["status"])
    if new_status not in CLOSING_STATUSES:
        raise ChreosError(
            f"the task is '{new_status}': close it with --status done or cancelled"
        )
    if requested is TaskStatus.DONE:
        statuses = graph.statuses_for(project, list(meta.get("dependencies") or []))
        require(done_message(doc.body, statuses), confirm)

    cleanup(task_dir, confirm)
    _save(path, doc, Phase.CLOSED, new_status)
    return Outcome(doc)
