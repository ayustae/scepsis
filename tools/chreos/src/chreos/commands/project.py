"""`chreos project` (design §12.2, §9)."""

import sys

import click

from chreos.cli_support import CONTEXT_SETTINGS, confirmer
from chreos.commands.common import (
    JSON_OPTION,
    emit_list,
    emit_show,
    load_context,
    modify_body,
    report_failures,
    run_edit,
    status_filter,
    warn_all,
)
from chreos.config import set_value
from chreos.errors import ChreosError
from chreos.frontmatter import load, save
from chreos.inputs import read_text_argument
from chreos.itemfields import split_labels, update_common
from chreos.items import load_item, load_items
from chreos.listing import SORT_KEYS, Filters
from chreos.lock import workspace_lock
from chreos.model import Kind, ProjectStatus
from chreos.operations import delete_project, rename_project
from chreos.projects import create_project
from chreos.sections import PROJECT_SECTIONS, append_text, read_section, validate_description, write_section
from chreos.timestamps import now
from chreos.workspace import Workspace

STATUSES = click.Choice([status.value for status in ProjectStatus])


def _project_file(workspace: Workspace, name: str):
    path = workspace.project_file(name)
    if not path.is_file():
        raise ChreosError(f"project '{name}' does not exist")
    return path


@click.group(context_settings=CONTEXT_SETTINGS)
def project():
    """Manage projects."""


@project.command()
@click.argument("name")
@click.option("-t", "--title", help="Title (default: NAME).")
@click.option("-s", "--summary", help="One or two sentences.")
@click.option("-l", "--label", "labels", multiple=True, help="Label; repeatable, comma-separated values accepted.")
@click.option("--status", type=STATUSES, default="active", show_default=True)
def create(name, title, summary, labels, status):
    """Create a project."""
    _, workspace = load_context()
    with workspace_lock(workspace.root):
        path = create_project(workspace, name, title=title, summary=summary, labels=split_labels(labels), status=status)
    click.echo(path)


@project.command()
@click.argument("name")
@click.option("-t", "--title", help="New title.")
@click.option("-s", "--summary", help="New summary; 'none' clears it.")
@click.option("-l", "--label", "labels", multiple=True, help="Add a label; repeatable.")
@click.option("--remove-label", "removed", multiple=True, help="Remove a label (exact match); repeatable.")
@click.option("--status", type=STATUSES)
def update(name, title, summary, labels, removed, status):
    """Change a project's title, summary, labels or status."""
    if title is None and summary is None and not labels and not removed and status is None:
        raise click.UsageError("nothing to update: give at least one option")
    _, workspace = load_context()
    with workspace_lock(workspace.root):
        path = _project_file(workspace, name)
        doc = load(path)
        changed, warnings = update_common(
            doc, title=title, summary=summary, add_labels=labels, remove_labels=removed,
            status=status, statuses=ProjectStatus,
        )
        if changed:
            doc.meta["updated"] = now()
            save(path, doc)
    warn_all(warnings)


@project.command()
@click.argument("name")
@click.option("-f", "--force", is_flag=True, help="Don't ask for confirmation.")
def delete(name, force):
    """Delete a project with all its tasks and decisions."""
    config, workspace = load_context()
    with workspace_lock(workspace.root):
        outcome = delete_project(workspace, name, default_project=config.default_project, confirm=confirmer(force))
    warn_all(outcome.warnings)


@project.command()
@click.argument("name")
@click.argument("new_name")
def rename(name, new_name):
    """Rename a project (references and the default project follow)."""
    config, workspace = load_context()
    with workspace_lock(workspace.root):
        outcome = rename_project(workspace, name, new_name, default_project=config.default_project)
        if outcome.renamed_default:
            set_value("defaults.project", new_name)
    warn_all(outcome.warnings)


@project.command(name="list")
@click.option("-l", "--label", "labels", multiple=True, help="Has this label (key or key=value); repeatable, AND.")
@click.option("-n", "--name", help="Name contains.")
@click.option("-t", "--title", help="Title contains.")
@click.option("-s", "--summary", help="Summary contains.")
@click.option("-S", "--search", help="Body contains.")
@click.option("--status", "statuses", type=STATUSES, multiple=True, help="Repeatable, OR (default: active).")
@click.option("--all", "show_all", is_flag=True, help="Include every status.")
@click.option("--sort", type=click.Choice(SORT_KEYS), default="name", show_default=True)
@JSON_OPTION
def list_(labels, name, title, summary, search, statuses, show_all, sort, as_json):
    """List projects."""
    config, workspace = load_context()
    items, failures = load_items([workspace.project_file(p) for p in workspace.projects()], Kind.PROJECT)
    report_failures(failures)
    filters = Filters(name, title, summary, search, list(labels), status_filter(statuses, show_all, {"active"}))
    emit_list(config, items, filters, sort, as_json, lambda item: (
        item.name, str(item.doc.meta.get("status", "")), str(item.doc.meta.get("title", ""))))


@project.command()
@click.argument("name")
@JSON_OPTION
def show(name, as_json):
    """Print a project file."""
    config, workspace = load_context()
    emit_show(config, load_item(_project_file(workspace, name), Kind.PROJECT), as_json)


@project.command()
@click.argument("name")
def edit(name):
    """Open a project file in $VISUAL/$EDITOR and validate it afterwards."""
    _, workspace = load_context()
    run_edit(_project_file(workspace, name), Kind.PROJECT, workspace)


@project.command()
@click.argument("name")
def path(name):
    """Print the absolute path of a project file."""
    _, workspace = load_context()
    click.echo(_project_file(workspace, name))


@project.group(context_settings=CONTEXT_SETTINGS)
def description():
    """Show or change a project's ## Description section."""


@description.command(name="show")
@click.argument("name")
def description_show(name):
    """Print the section content."""
    _, workspace = load_context()
    content = read_section(load(_project_file(workspace, name)).body, "Description") or ""
    if content:
        click.echo(content)


def _write_description(name: str, text: str | None, append: bool) -> None:
    content = validate_description(read_text_argument(text, sys.stdin))
    _, workspace = load_context()
    write = append_text if append else write_section
    modify_body(workspace, _project_file(workspace, name),
                lambda body: write(body, "Description", content, PROJECT_SECTIONS))


@description.command(name="append")
@click.argument("name")
@click.argument("text", required=False)
def description_append(name, text):
    """Add TEXT (or standard input) after the existing content."""
    _write_description(name, text, append=True)


@description.command(name="replace")
@click.argument("name")
@click.argument("text", required=False)
def description_replace(name, text):
    """Replace the content with TEXT (or standard input); empty text clears it."""
    _write_description(name, text, append=False)
