"""Helpers shared by the item command groups (project, task, decision)."""

import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

import click

from chreos import cli_support
from chreos.cli_support import emit_json, wants_json, warn
from chreos.config import Config, load_config
from chreos.editing import Checks, edit_item
from chreos.errors import ChreosError
from chreos.frontmatter import load, save
from chreos.inputs import read_text_argument
from chreos.items import LoadedItem, LoadFailure
from chreos.listing import Filters, filter_items, sort_items
from chreos.lock import workspace_lock
from chreos.model import Kind
from chreos.output import list_entry, show_entry, table
from chreos.sections import append_text, read_section, validate_description, write_section
from chreos.timestamps import now
from chreos.workspace import Workspace

JSON_OPTION = click.option("--json", "as_json", is_flag=True, help="Output JSON.")
PROJECT_OPTION = click.option(
    "-P", "--project", "project_opt", metavar="PROJECT", help="Project (default: the configured default project)."
)


def load_context() -> tuple[Config, Workspace]:
    config = load_config()
    return config, Workspace(config.workspace)


def warn_all(messages: Iterable[str]) -> None:
    for message in messages:
        warn(message)


def report_failures(failures: Iterable[LoadFailure]) -> None:
    warn_all(f"skipped {failure.message}" for failure in failures)


def emit_list(
    config: Config,
    items: list[LoadedItem],
    filters: Filters,
    sort: str,
    as_json: bool,
    row: Callable[[LoadedItem], tuple[str, ...]],
    extra: Callable[[LoadedItem], bool] | None = None,
) -> None:
    selected = sort_items(filter_items(items, filters, extra), sort)
    if wants_json(as_json, config.output_format):
        emit_json([list_entry(item) for item in selected])
    else:
        for line in table([row(item) for item in selected]):
            click.echo(line)


def emit_show(config: Config, item: LoadedItem, as_json: bool, extra: dict | None = None) -> None:
    if wants_json(as_json, config.output_format):
        emit_json({**show_entry(item), **(extra or {})})
    else:
        click.echo(item.path.read_text(encoding="utf-8"), nl=False)


def run_edit(path: Path, kind: Kind, workspace: Workspace, extra_checks: Checks | None = None) -> None:
    if not cli_support.is_interactive():
        raise ChreosError(
            f"edit needs a terminal; use 'chreos {kind} update' and the section commands "
            f"(see 'chreos {kind} --help'), or 'path' to get the file and edit it directly"
        )
    result = edit_item(path, kind, workspace.root, extra_checks=extra_checks)
    warn_all(result.warnings)
    if result.errors:
        listing = "\n".join(f"  - {error}" for error in result.errors)
        raise ChreosError(f"the edited file has validation errors:\n{listing}")


def status_filter(statuses: tuple[str, ...], show_all: bool, default: set[str]) -> set[str] | None:
    if show_all:
        return None
    return set(statuses) if statuses else default


def modify_body(workspace: Workspace, path: Path, fn: Callable[[str], str]) -> None:
    """Rewrite an item's body under the lock and bump `updated` (§9: every append/replace)."""
    with workspace_lock(workspace.root):
        doc = load(path)
        doc.body = fn(doc.body)
        doc.meta["updated"] = now()
        save(path, doc)


def show_description(path: Path) -> None:
    """`description show`: the raw `## Description` content, nothing if empty or missing."""
    content = read_section(load(path).body, "Description")
    if content:
        click.echo(content)


def read_description(text: str | None) -> str:
    """The TEXT argument or standard input, validated as description content (§9)."""
    return validate_description(read_text_argument(text, sys.stdin))


def write_description(workspace: Workspace, path: Path, content: str, append: bool, order: Sequence[str]) -> None:
    """`description append|replace` on an item whose sections follow `order`."""
    write = append_text if append else write_section
    modify_body(workspace, path, lambda body: write(body, "Description", content, order))


def resolve(text: str, project_opt: str | None) -> tuple[Config, Workspace, str, str]:
    """Context plus a NAME argument resolved with -P (`<name>` or `<project>/<name>`)."""
    config, workspace = load_context()
    project, name = workspace.resolve_item_name(text, project_opt, config.default_project)
    return config, workspace, project, name


def emit_dependency_show(config: Config, item: LoadedItem, graph, node, as_json: bool) -> None:
    """`show` for tasks and decisions: the file plus dependency statuses and dependents."""
    statuses = graph.dependency_statuses(node) if node in graph else []
    dependents = [str(n) for n in graph.dependents(node)]
    emit_show(config, item, as_json, {
        "dependencies": [{"ref": s.ref, "status": s.status, "satisfied": s.satisfied} for s in statuses],
        "dependents": dependents,
    })
    if wants_json(as_json, config.output_format):
        return
    if statuses:
        click.echo("\nDependencies:")
        rows = [(s.ref, s.status or "unresolved", "satisfied" if s.satisfied else "unsatisfied") for s in statuses]
        for line in table(rows):
            click.echo(f"  {line}")
    if dependents:
        click.echo("\nDependents:")
        for dependent in dependents:
            click.echo(f"  {dependent}")
