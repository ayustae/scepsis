"""`chreos decision` (design §12.4)."""

import click

from chreos.cli_support import CONTEXT_SETTINGS, confirmer
from chreos.commands.common import (
    JSON_OPTION,
    PROJECT_OPTION,
    emit_dependency_show,
    emit_list,
    load_context,
    read_description,
    report_failures,
    resolve,
    run_edit,
    show_description,
    status_filter,
    warn_all,
    write_description,
)
from chreos.decisions import create_decision, update_decision
from chreos.dependencies import dependency_checks
from chreos.errors import ChreosError
from chreos.graph import Graph, Node
from chreos.items import load_item, load_items
from chreos.listing import SORT_KEYS, Filters
from chreos.lock import workspace_lock
from chreos.model import DecisionStatus, Kind
from chreos.operations import delete_decision, move_decision, rename_decision
from chreos.refs import parse_ref
from chreos.sections import DECISION_SECTIONS
from chreos.workspace import Workspace

STATUSES = click.Choice([status.value for status in DecisionStatus])
DEPS_OPTION = click.option("--dep", "--depends-on", "deps", multiple=True, metavar="REF",
                           help="task:… or decision:…; repeatable.")
FORCE_OPTION = click.option("-f", "--force", is_flag=True,
                            help="Skip the confirmation for decided with unsatisfied dependencies.")


@click.group(context_settings=CONTEXT_SETTINGS)
def decision():
    """Manage decisions."""


def _decision_file(workspace: Workspace, project: str, name: str):
    if not workspace.project_exists(project):
        raise ChreosError(f"project '{project}' does not exist")
    path = workspace.decision_file(project, name)
    if not path.is_file():
        raise ChreosError(f"decision '{project}/{name}' does not exist")
    return path


@decision.command()
@click.argument("name")
@PROJECT_OPTION
@click.option("-t", "--title", help="Title (default: NAME).")
@click.option("-s", "--summary", help="One or two sentences.")
@click.option("-l", "--label", "labels", multiple=True, help="Label; repeatable, comma-separated values accepted.")
@DEPS_OPTION
@click.option("--status", type=STATUSES, default="pending", show_default=True)
@FORCE_OPTION
def create(name, project_opt, title, summary, labels, deps, status, force):
    """Create a decision."""
    _, workspace, project, name = resolve(name, project_opt)
    with workspace_lock(workspace.root):
        path = create_decision(
            workspace, Graph.load(workspace), project, name, confirm=confirmer(force), title=title,
            summary=summary, labels=labels, dependencies=deps, status=status,
        )
    click.echo(path)


@decision.command()
@click.argument("name")
@PROJECT_OPTION
@click.option("-t", "--title", help="New title.")
@click.option("-s", "--summary", help="New summary; 'none' clears it.")
@click.option("-l", "--label", "labels", multiple=True, help="Add a label; repeatable.")
@click.option("--remove-label", "removed_labels", multiple=True, help="Remove a label (exact match); repeatable.")
@click.option("--status", type=STATUSES)
@click.option("--dep", "--depends-on", "deps", multiple=True, metavar="REF", help="Add a dependency; repeatable.")
@click.option("--remove-dep", "removed_deps", multiple=True, metavar="REF", help="Remove a dependency; repeatable.")
@FORCE_OPTION
def update(name, project_opt, title, summary, labels, removed_labels, status, deps, removed_deps, force):
    """Change a decision's fields, status or dependencies."""
    if title is None and summary is None and status is None and not (labels or removed_labels or deps or removed_deps):
        raise click.UsageError("nothing to update: give at least one option")
    _, workspace, project, name = resolve(name, project_opt)
    with workspace_lock(workspace.root):
        warnings = update_decision(
            workspace, Graph.load(workspace), project, name, confirm=confirmer(force), title=title,
            summary=summary, add_labels=labels, remove_labels=removed_labels, status=status,
            add_deps=deps, remove_deps=removed_deps,
        )
    warn_all(warnings)


@decision.command()
@click.argument("name")
@PROJECT_OPTION
@click.option("-f", "--force", is_flag=True, help="Don't ask for confirmation.")
def delete(name, project_opt, force):
    """Delete a decision permanently; references to it are removed."""
    _, workspace, project, name = resolve(name, project_opt)
    with workspace_lock(workspace.root):
        warn_all(delete_decision(workspace, project, name, confirm=confirmer(force)).warnings)


@decision.command()
@click.argument("name")
@click.argument("new_name")
@PROJECT_OPTION
def rename(name, new_name, project_opt):
    """Rename a decision (references follow)."""
    _, workspace, project, name = resolve(name, project_opt)
    with workspace_lock(workspace.root):
        warn_all(rename_decision(workspace, project, name, new_name).warnings)


@decision.command()
@click.argument("name")
@click.argument("destination", metavar="PROJECT")
@PROJECT_OPTION
def move(name, destination, project_opt):
    """Move a decision to another project (references follow)."""
    _, workspace, project, name = resolve(name, project_opt)
    with workspace_lock(workspace.root):
        warn_all(move_decision(workspace, project, name, destination).warnings)


@decision.command(name="list")
@PROJECT_OPTION
@click.option("--all-projects", is_flag=True, help="List decisions of every project.")
@click.option("-l", "--label", "labels", multiple=True, help="Has this label (key or key=value); repeatable, AND.")
@click.option("-n", "--name", help="Name contains.")
@click.option("-t", "--title", help="Title contains.")
@click.option("-s", "--summary", help="Summary contains.")
@click.option("-S", "--search", help="Body contains.")
@click.option("--status", "statuses", type=STATUSES, multiple=True, help="Repeatable, OR (default: pending).")
@click.option("--all", "show_all", is_flag=True, help="Include every status.")
@click.option("--depends-on", metavar="REF", help="Only decisions that depend on REF.")
@click.option("--sort", type=click.Choice(SORT_KEYS), default="name", show_default=True)
@JSON_OPTION
def list_(project_opt, all_projects, labels, name, title, summary, search, statuses, show_all, depends_on, sort, as_json):
    """List decisions."""
    config, workspace = load_context()
    if all_projects and project_opt:
        raise click.UsageError("-P and --all-projects can't be combined")
    project = project_opt or config.default_project
    if not all_projects and not workspace.project_exists(project):
        raise ChreosError(f"project '{project}' does not exist")
    projects = workspace.projects() if all_projects else [project]
    paths = [workspace.decision_file(p, n) for p in projects for n in workspace.decision_names(p)]
    items, failures = load_items(paths, Kind.DECISION)
    report_failures(failures)

    extra = None
    if depends_on:
        graph = Graph.load(workspace)
        dependents = set(graph.dependents(Node.of(parse_ref(depends_on), project)))
        extra = lambda item: Node(Kind.DECISION, item.project, item.name) in dependents  # noqa: E731
    filters = Filters(name, title, summary, search, list(labels), status_filter(statuses, show_all, {"pending"}))

    def row(item):
        label = f"{item.project}/{item.name}" if all_projects else item.name
        return (label, str(item.doc.meta.get("status", "")), str(item.doc.meta.get("title", "")))

    emit_list(config, items, filters, sort, as_json, row, extra=extra)


@decision.command()
@click.argument("name")
@PROJECT_OPTION
@JSON_OPTION
def show(name, project_opt, as_json):
    """Print a decision with its dependency statuses and dependents."""
    config, workspace, project, name = resolve(name, project_opt)
    item = load_item(_decision_file(workspace, project, name), Kind.DECISION)
    emit_dependency_show(config, item, Graph.load(workspace), Node(Kind.DECISION, project, name), as_json)


@decision.command()
@click.argument("name")
@PROJECT_OPTION
def edit(name, project_opt):
    """Open a decision in $VISUAL/$EDITOR and validate it afterwards."""
    _, workspace, project, name = resolve(name, project_opt)
    node = Node(Kind.DECISION, project, name)
    run_edit(_decision_file(workspace, project, name), Kind.DECISION, workspace,
             extra_checks=lambda doc: (dependency_checks(workspace, node), []))


@decision.command()
@click.argument("name")
@PROJECT_OPTION
def path(name, project_opt):
    """Print the absolute path of a decision file."""
    _, workspace, project, name = resolve(name, project_opt)
    click.echo(_decision_file(workspace, project, name))


# Sections (§9)


@decision.group(context_settings=CONTEXT_SETTINGS)
def description():
    """Show or change a decision's ## Description section."""


@description.command(name="show")
@click.argument("name")
@PROJECT_OPTION
def description_show(name, project_opt):
    """Print the section content."""
    _, workspace, project, name = resolve(name, project_opt)
    show_description(_decision_file(workspace, project, name))


def _write_description(name, project_opt, text, append):
    content = read_description(text)
    _, workspace, project, name = resolve(name, project_opt)
    write_description(workspace, _decision_file(workspace, project, name), content, append, DECISION_SECTIONS)


@description.command(name="append")
@click.argument("name")
@click.argument("text", required=False)
@PROJECT_OPTION
def description_append(name, text, project_opt):
    """Add TEXT (or standard input) after the existing content."""
    _write_description(name, project_opt, text, append=True)


@description.command(name="replace")
@click.argument("name")
@click.argument("text", required=False)
@PROJECT_OPTION
def description_replace(name, text, project_opt):
    """Replace the content with TEXT (or standard input); empty text clears it."""
    _write_description(name, project_opt, text, append=False)
