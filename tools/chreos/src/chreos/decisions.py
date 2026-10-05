"""Decision rules behind `decision create|update` (design §3.4, §6, §10, §12.4)."""

from collections.abc import Iterable
from pathlib import Path

from chreos.confirmations import Confirm, decided_message, require
from chreos.dependencies import apply_dependency_changes
from chreos.errors import ChreosError
from chreos.frontmatter import dump, load, save
from chreos.graph import Graph, Node
from chreos.itemfields import parse_status, split_labels, update_common
from chreos.model import DecisionStatus, Kind, validate_name
from chreos.templates import render
from chreos.timestamps import now
from chreos.workspace import Workspace


def _require_project(workspace: Workspace, project: str) -> None:
    if not workspace.project_exists(project):
        raise ChreosError(f"project '{project}' does not exist")


def _confirm_decided(graph: Graph, project: str, dependencies: list, confirm: Confirm) -> None:
    statuses = graph.statuses_for(project, [entry for entry in dependencies if isinstance(entry, str)])
    require(decided_message(statuses), confirm)


def create_decision(
    workspace: Workspace,
    graph: Graph,
    project: str,
    name: str,
    *,
    confirm: Confirm,
    title: str | None = None,
    summary: str | None = None,
    labels: Iterable[str] = (),
    dependencies: Iterable[str] = (),
    status: str = DecisionStatus.PENDING,
) -> Path:
    """Create a decision file; caller holds the lock."""
    _require_project(workspace, project)
    validate_name(name)
    workspace.ensure_free(Kind.DECISION, project, name)
    new_status = parse_status(status, DecisionStatus)
    dependencies = list(dependencies)
    graph.check_new_dependencies(Node(Kind.DECISION, project, name), dependencies)
    fields = {"status": new_status, "labels": split_labels(labels), "dependencies": dependencies}
    doc = render(Kind.DECISION, name=name, title=title, summary=summary, project=project, fields=fields)
    if new_status is DecisionStatus.DECIDED:
        _confirm_decided(graph, project, dependencies, confirm)
    workspace.ensure_project_dirs(project)
    path = workspace.decision_file(project, name)
    save(path, doc)
    return path


def update_decision(
    workspace: Workspace,
    graph: Graph,
    project: str,
    name: str,
    *,
    confirm: Confirm,
    title: str | None = None,
    summary: str | None = None,
    add_labels: Iterable[str] = (),
    remove_labels: Iterable[str] = (),
    status: str | None = None,
    add_deps: Iterable[str] = (),
    remove_deps: Iterable[str] = (),
) -> list[str]:
    """Apply `decision update` with a single write, after every check and confirmation."""
    _require_project(workspace, project)
    path = workspace.decision_file(project, name)
    if not path.is_file():
        raise ChreosError(f"decision '{project}/{name}' does not exist")
    doc = load(path)
    original = dump(doc)
    old_status = doc.meta.get("status")
    _, warnings = update_common(
        doc, title=title, summary=summary, add_labels=add_labels, remove_labels=remove_labels,
        status=status, statuses=DecisionStatus,
    )
    node = Node(Kind.DECISION, project, name)
    warnings += apply_dependency_changes(doc.meta, graph, node, add=add_deps, remove=remove_deps)
    if doc.meta.get("status") == DecisionStatus.DECIDED and old_status != DecisionStatus.DECIDED:
        _confirm_decided(graph, project, doc.meta["dependencies"], confirm)
    if dump(doc) != original:
        doc.meta["updated"] = now()
        save(path, doc)
    return warnings
