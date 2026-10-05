"""Task rules behind `task create|update|list|show|edit` (design §3.3, §6, §10, §11, §12.3)."""

from collections.abc import Callable, Iterable
from datetime import date, datetime

from chreos.confirmations import Confirm, done_message, require
from chreos.dependencies import apply_dependency_changes, dependency_checks
from chreos.errors import ChreosError
from chreos.frontmatter import Document, dump, load, save
from chreos.graph import CLOSED_TASK_STATUSES, Graph, Node
from chreos.itemfields import split_labels, update_common
from chreos.items import LoadedItem
from chreos.lists import ListKind, read_items
from chreos.model import (
    Kind,
    Phase,
    SourceType,
    TaskStatus,
    check_status_for_phase,
    parse_assignee,
    parse_due,
    parse_optional,
    parse_priority,
    validate_name,
)
from chreos.paths import parse_source_path
from chreos.refs import validate_reference
from chreos.sources import Bases, Source, check_source_change, source_warnings
from chreos.templates import render
from chreos.timestamps import now
from chreos.workspace import Workspace


def resolve_task(workspace: Workspace, text: str, project_opt: str | None, default_project: str) -> tuple[str, str]:
    """A task NAME argument: `<name>` (in -P or the default project) or `<project>/<name>`."""
    return workspace.resolve_item_name(text, project_opt, default_project)


def _require_project(workspace: Workspace, project: str) -> None:
    if not workspace.project_exists(project):
        raise ChreosError(f"project '{project}' does not exist")


def _source(source_type: str | None, source_path: str | None, current: Source | None, bases: Bases):
    """The new source mapping and its warnings, or (None, []) if nothing was given."""
    if source_type is None and source_path is None:
        return None, []
    new_type = source_type or (current.type if current else None)
    new_path = source_path or (current.path if current else None)
    if new_type is None or new_path is None:
        raise ChreosError("--source-type and --source-path must be given together")
    try:
        new_type = SourceType(new_type)
    except ValueError:
        raise ChreosError(f"invalid source type {new_type!r} (allowed: git, local)") from None
    source = Source(new_type, parse_source_path(new_path))
    return {"type": source.type, "path": source.path}, source_warnings(source, bases)


def create_task(
    workspace: Workspace,
    graph: Graph,
    project: str,
    name: str,
    *,
    bases: Bases,
    title: str | None = None,
    summary: str | None = None,
    labels: Iterable[str] = (),
    source_type: str | None = None,
    source_path: str | None = None,
    priority: str | None = None,
    due: str | None = None,
    assignee: str | None = None,
    dependencies: Iterable[str] = (),
):
    """Create a closed task with status `new`; returns (path, warnings). Caller holds the lock."""
    _require_project(workspace, project)
    validate_name(name)
    workspace.ensure_free(Kind.TASK, project, name)
    source, warnings = _source(source_type, source_path, None, bases)
    dependencies = list(dependencies)
    graph.check_new_dependencies(Node(Kind.TASK, project, name), dependencies)
    fields = {
        "source": source,
        "priority": parse_priority(priority) if priority is not None else None,
        "due": parse_due(due) if due is not None else None,
        "assignee": parse_assignee(assignee) if assignee is not None else None,
        "labels": split_labels(labels),
        "dependencies": dependencies,
    }
    doc = render(Kind.TASK, name=name, title=title, summary=summary, project=project, fields=fields)
    workspace.ensure_project_dirs(project)
    path = workspace.live_task_file(project, name)
    path.parent.mkdir()
    save(path, doc)
    return path, warnings


def set_assignee(meta, value: str, confirm: Confirm) -> bool:
    """Set or clear (`none`) the assignee; replacing another assignee needs confirmation."""
    new = parse_optional(value, parse_assignee)
    current = meta.get("assignee")
    if new == current:
        return False
    if current and new is not None:
        require(f"The task is assigned to '{current}'. Reassign it to '{new}'?", confirm)
    meta["assignee"] = new
    return True


def _load_live(workspace: Workspace, project: str, name: str):
    _require_project(workspace, project)
    path = workspace.live_task_file(project, name)
    if not path.is_file():
        if workspace.archived_task_file(project, name).is_file():
            raise ChreosError(f"task '{project}/{name}' is archived; restore it first")
        raise ChreosError(f"task '{project}/{name}' does not exist")
    return path, load(path)


def update_task(
    workspace: Workspace,
    graph: Graph,
    project: str,
    name: str,
    *,
    confirm: Confirm,
    bases: Bases,
    title: str | None = None,
    summary: str | None = None,
    add_labels: Iterable[str] = (),
    remove_labels: Iterable[str] = (),
    status: str | None = None,
    source_type: str | None = None,
    source_path: str | None = None,
    priority: str | None = None,
    due: str | None = None,
    assignee: str | None = None,
    add_deps: Iterable[str] = (),
    remove_deps: Iterable[str] = (),
) -> list[str]:
    """Apply `task update`; every check and confirmation happens before the single write."""
    path, doc = _load_live(workspace, project, name)
    original = dump(doc)
    meta = doc.meta
    node = Node(Kind.TASK, project, name)
    _, warnings = update_common(
        doc, title=title, summary=summary, add_labels=add_labels, remove_labels=remove_labels,
        status=None, statuses=TaskStatus,
    )

    old_status = meta.get("status")
    if status is not None:
        try:
            new_status = TaskStatus(status)
        except ValueError:
            raise ChreosError(f"invalid task status {status!r}") from None
        check_status_for_phase(Phase(meta.get("phase")), new_status)
        meta["status"] = new_status

    if source_type is not None or source_path is not None:
        check_source_change(meta.get("phase"))
        source, source_problems = _source(source_type, source_path, Source.from_meta(meta.get("source")), bases)
        meta["source"] = source
        warnings += source_problems
    if priority is not None:
        meta["priority"] = parse_optional(priority, parse_priority)
    if due is not None:
        meta["due"] = parse_optional(due, parse_due)

    warnings += apply_dependency_changes(meta, graph, node, add=add_deps, remove=remove_deps)
    dependencies = meta["dependencies"]

    if meta.get("status") == TaskStatus.DONE and old_status != TaskStatus.DONE:
        statuses = graph.statuses_for(project, [e for e in dependencies if isinstance(e, str)])
        require(done_message(doc.body, statuses), confirm)
    if assignee is not None:
        set_assignee(meta, assignee, confirm)

    if dump(doc) != original:
        meta["updated"] = now()
        save(path, doc)
    return warnings


def task_checks(workspace: Workspace, project: str, name: str) -> Callable[[Document], tuple[list[str], list[str]]]:
    """Extra `edit` checks for a task: dependencies and `## References` entries resolve."""

    def checks(doc: Document) -> tuple[list[str], list[str]]:
        errors = dependency_checks(workspace, Node(Kind.TASK, project, name))
        for item in read_items(doc.body, "References", ListKind.BULLETS):
            try:
                validate_reference(workspace, project, item.text)
            except ChreosError as error:
                errors.append(f"## References: {error}")
        return errors, []

    return checks


def _is_date(value: object) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def task_predicate(
    graph: Graph,
    *,
    today: date,
    phases: set[str] | None = None,
    priorities: set[str] | None = None,
    assignees: set[str] | None = None,
    unassigned: bool = False,
    due_before: date | None = None,
    overdue: bool = False,
    ready: bool = False,
    depends_on: Node | None = None,
) -> Callable[[LoadedItem], bool]:
    """The task-only `list` filters (§12.3), combined with AND."""
    ready_nodes = set(graph.ready_tasks()) if ready else set()
    dependents = set(graph.dependents(depends_on)) if depends_on else set()

    def predicate(item: LoadedItem) -> bool:
        meta = item.doc.meta
        due = meta.get("due")
        node = Node(Kind.TASK, item.project, item.name)
        return (
            (not phases or meta.get("phase") in phases)
            and (not priorities or meta.get("priority") in priorities)
            and (not assignees or meta.get("assignee") in assignees)
            and (not unassigned or not meta.get("assignee"))
            and (due_before is None or (_is_date(due) and due < due_before))
            and (not overdue or (_is_date(due) and due < today and meta.get("status") not in CLOSED_TASK_STATUSES))
            and (not ready or node in ready_nodes)
            and (depends_on is None or node in dependents)
        )

    return predicate
