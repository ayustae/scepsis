"""`chreos task` (design §12.3, §9)."""

import sys
from datetime import date

import click

from chreos.cli_support import CONTEXT_SETTINGS, confirmer, emit_json, wants_json
from chreos.commands.common import (
    JSON_OPTION,
    PROJECT_OPTION,
    emit_dependency_show,
    emit_list,
    load_context,
    modify_body,
    report_failures,
    resolve,
    run_edit,
    status_filter,
    warn_all,
)
from chreos.frontmatter import load
from chreos.inputs import read_text_argument
from chreos.lifecycle import close_task, open_task
from chreos.lists import ListKind, append_items, read_items, replace_items
from chreos.operations import archive_task, delete_task, move_task, rename_task, restore_task
from chreos.refs import classify_reference, validate_reference
from chreos.sections import TASK_SECTIONS, append_text, read_section, validate_description, write_section
from chreos.errors import ChreosError
from chreos.graph import Graph, Node
from chreos.items import load_item, load_items
from chreos.listing import TASK_SORT_KEYS, Filters
from chreos.lock import workspace_lock
from chreos.model import Kind, Phase, Priority, SourceType, TaskStatus, parse_due
from chreos.refs import parse_ref
from chreos.tasks import create_task, task_checks, task_predicate, update_task
from chreos.workspace import Workspace

STATUSES = click.Choice([s.value for s in TaskStatus])
PRIORITIES = click.Choice([p.value for p in Priority])
SOURCE_TYPES = click.Choice([t.value for t in SourceType])
OPEN_STATUSES = {TaskStatus.NEW, TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.ON_HOLD}


@click.group(context_settings=CONTEXT_SETTINGS)
def task():
    """Manage tasks."""


def _task_file(workspace: Workspace, project: str, name: str):
    """The task's file, live or archived."""
    if not workspace.project_exists(project):
        raise ChreosError(f"project '{project}' does not exist")
    for path in (workspace.live_task_file(project, name), workspace.archived_task_file(project, name)):
        if path.is_file():
            return path
    raise ChreosError(f"task '{project}/{name}' does not exist")


@task.command()
@click.argument("name")
@PROJECT_OPTION
@click.option("-t", "--title", help="Title (default: NAME).")
@click.option("-s", "--summary", help="One or two sentences.")
@click.option("-l", "--label", "labels", multiple=True, help="Label; repeatable, comma-separated values accepted.")
@click.option("--source-type", type=SOURCE_TYPES, help="Set together with --source-path.")
@click.option("--source-path", metavar="PATH", help="Absolute, or relative to the configured base folder.")
@click.option("--priority", type=PRIORITIES)
@click.option("--due", metavar="DATE", help="YYYY-MM-DD.")
@click.option("--assignee", help="Person or agent working on the task.")
@click.option("--dep", "--depends-on", "deps", multiple=True, metavar="REF", help="task:… or decision:…; repeatable.")
def create(name, project_opt, title, summary, labels, source_type, source_path, priority, due, assignee, deps):
    """Create a task (closed, status new)."""
    config, workspace, project, name = resolve(name, project_opt)
    with workspace_lock(workspace.root):
        path, warnings = create_task(
            workspace, Graph.load(workspace), project, name, bases=config.bases, title=title, summary=summary,
            labels=labels, source_type=source_type, source_path=source_path, priority=priority, due=due,
            assignee=assignee, dependencies=deps,
        )
    click.echo(path)
    warn_all(warnings)


@task.command()
@click.argument("name")
@PROJECT_OPTION
@click.option("-t", "--title", help="New title.")
@click.option("-s", "--summary", help="New summary; 'none' clears it.")
@click.option("-l", "--label", "labels", multiple=True, help="Add a label; repeatable.")
@click.option("--remove-label", "removed_labels", multiple=True, help="Remove a label (exact match); repeatable.")
@click.option("--status", type=STATUSES, help="Must be allowed in the current phase.")
@click.option("--source-type", type=SOURCE_TYPES, help="Closed tasks only.")
@click.option("--source-path", metavar="PATH", help="Closed tasks only.")
@click.option("--priority", type=click.Choice([*PRIORITIES.choices, "none"]))
@click.option("--due", metavar="DATE|none")
@click.option("--assignee", metavar="TEXT|none", help="Replacing another assignee needs confirmation.")
@click.option("--dep", "--depends-on", "deps", multiple=True, metavar="REF", help="Add a dependency; repeatable.")
@click.option("--remove-dep", "removed_deps", multiple=True, metavar="REF", help="Remove a dependency; repeatable.")
@click.option("-f", "--force", is_flag=True, help="Skip confirmations (done, reassigning).")
def update(name, project_opt, title, summary, labels, removed_labels, status, source_type, source_path,
           priority, due, assignee, deps, removed_deps, force):
    """Change a task's fields, status or dependencies."""
    options = (title, summary, status, source_type, source_path, priority, due, assignee)
    if all(value is None for value in options) and not (labels or removed_labels or deps or removed_deps):
        raise click.UsageError("nothing to update: give at least one option")
    config, workspace, project, name = resolve(name, project_opt)
    with workspace_lock(workspace.root):
        warnings = update_task(
            workspace, Graph.load(workspace), project, name, confirm=confirmer(force), bases=config.bases,
            title=title, summary=summary, add_labels=labels, remove_labels=removed_labels, status=status,
            source_type=source_type, source_path=source_path, priority=priority, due=due, assignee=assignee,
            add_deps=deps, remove_deps=removed_deps,
        )
    warn_all(warnings)


@task.command(name="list")
@PROJECT_OPTION
@click.option("--all-projects", is_flag=True, help="List tasks of every project.")
@click.option("-l", "--label", "labels", multiple=True, help="Has this label (key or key=value); repeatable, AND.")
@click.option("-n", "--name", help="Name contains.")
@click.option("-t", "--title", help="Title contains.")
@click.option("-s", "--summary", help="Summary contains.")
@click.option("-S", "--search", help="Body contains.")
@click.option("--phase", "phases", type=click.Choice([p.value for p in Phase]), multiple=True, help="Repeatable, OR.")
@click.option("--status", "statuses", type=STATUSES, multiple=True, help="Repeatable, OR (default hides done and cancelled).")
@click.option("--all", "show_all", is_flag=True, help="Include every status.")
@click.option("--ready", is_flag=True, help="Only tasks that can be worked on next.")
@click.option("--depends-on", metavar="REF", help="Only tasks that depend on REF.")
@click.option("--priority", "priorities", type=PRIORITIES, multiple=True, help="Repeatable, OR.")
@click.option("--due-before", metavar="DATE", help="Due strictly before DATE.")
@click.option("--overdue", is_flag=True, help="Due before today and not done or cancelled.")
@click.option("--assignee", "assignees", multiple=True, help="Repeatable, OR.")
@click.option("--unassigned", is_flag=True, help="Only tasks without an assignee.")
@click.option("--archived", is_flag=True, help="List archived tasks instead of live ones.")
@click.option("--sort", type=click.Choice(TASK_SORT_KEYS), default="name", show_default=True)
@JSON_OPTION
def list_(project_opt, all_projects, labels, name, title, summary, search, phases, statuses, show_all, ready,
          depends_on, priorities, due_before, overdue, assignees, unassigned, archived, sort, as_json):
    """List tasks."""
    config, workspace = load_context()
    if all_projects and project_opt:
        raise click.UsageError("-P and --all-projects can't be combined")
    project = project_opt or config.default_project
    projects = workspace.projects() if all_projects else [project]
    if not all_projects and not workspace.project_exists(project):
        raise ChreosError(f"project '{project}' does not exist")
    path_of = workspace.archived_task_file if archived else workspace.live_task_file
    paths = [path_of(p, n) for p in projects for n in workspace.task_names(p, archived=archived)]
    items, failures = load_items(paths, Kind.TASK)
    report_failures(failures)

    graph = Graph.load(workspace) if ready or depends_on else Graph()
    target = Node.of(parse_ref(depends_on), project) if depends_on else None
    predicate = task_predicate(
        graph, today=date.today(), phases=set(phases), priorities=set(priorities), assignees=set(assignees),
        unassigned=unassigned, due_before=parse_due(due_before) if due_before else None, overdue=overdue,
        ready=ready, depends_on=target,
    )
    filters = Filters(name, title, summary, search, list(labels),
                      status_filter(statuses, show_all, {s.value for s in OPEN_STATUSES}))

    def row(item):
        meta = item.doc.meta
        label = f"{item.project}/{item.name}" if all_projects else item.name
        due = meta.get("due")
        return (label, str(meta.get("phase", "")), str(meta.get("status", "")),
                str(meta.get("priority") or "-"), str(due) if due else "-", str(meta.get("title", "")))

    emit_list(config, items, filters, sort, as_json, row, extra=predicate)


@task.command()
@click.argument("name")
@PROJECT_OPTION
@JSON_OPTION
def show(name, project_opt, as_json):
    """Print a task with its dependency statuses and dependents."""
    config, workspace, project, name = resolve(name, project_opt)
    item = load_item(_task_file(workspace, project, name), Kind.TASK)
    emit_dependency_show(config, item, Graph.load(workspace), Node(Kind.TASK, project, name), as_json)


@task.command()
@click.argument("name")
@PROJECT_OPTION
@click.option("--work", is_flag=True, help="Print the work/ folder of an open task instead.")
def path(name, project_opt, work):
    """Print the absolute path of a task file."""
    _, workspace, project, name = resolve(name, project_opt)
    file = _task_file(workspace, project, name)
    if not work:
        click.echo(file)
        return
    meta = load_item(file, Kind.TASK).doc.meta
    if file != workspace.live_task_file(project, name) or meta.get("phase") != Phase.OPEN:
        raise ChreosError(f"task '{project}/{name}' is not open, so it has no work/ folder")
    click.echo(file.parent / "work")


@task.command()
@click.argument("name")
@PROJECT_OPTION
def edit(name, project_opt):
    """Open a task file in $VISUAL/$EDITOR and validate it afterwards."""
    _, workspace, project, name = resolve(name, project_opt)
    file = _task_file(workspace, project, name)
    if file != workspace.live_task_file(project, name):
        raise ChreosError(f"task '{project}/{name}' is archived; restore it first")
    run_edit(file, Kind.TASK, workspace, extra_checks=task_checks(workspace, project, name))


# Lifecycle (§11)


@task.command(name="open")
@click.argument("name")
@PROJECT_OPTION
@click.option("--status", type=click.Choice([s.value for s in TaskStatus if s is not TaskStatus.NEW]),
              help="Default: todo or on-hold, from dependencies.")
@click.option("--assignee", help="Assign while opening (same rule as update).")
@click.option("--recreate", is_flag=True, help="Remove and recreate work/ even if it exists.")
@click.option("--base", metavar="REF", help="git: starting point for a new branch (default: origin/HEAD, else HEAD).")
@click.option("-f", "--force", is_flag=True, help="Skip confirmations (work/ cleanup, done, reassigning).")
def open_(name, project_opt, status, assignee, recreate, base, force):
    """Open a task: create work/ and make it workable. Prints the work/ path."""
    config, workspace, project, name = resolve(name, project_opt)
    with workspace_lock(workspace.root):
        outcome = open_task(
            workspace, Graph.load(workspace), project, name, bases=config.bases, confirm=confirmer(force),
            status=status, recreate=recreate, base=base, assignee=assignee,
        )
    click.echo(workspace.live_task_file(project, name).parent / "work")
    click.echo(f"task '{project}/{name}' is open ({outcome.doc.meta['status']})", err=True)
    warn_all(outcome.warnings)


@task.command()
@click.argument("name")
@PROJECT_OPTION
@click.option("--status", type=click.Choice(["done", "cancelled"]), help="Set before closing.")
@click.option("-f", "--force", is_flag=True, help="Skip confirmations (cleanup, done).")
def close(name, project_opt, status, force):
    """Close a task: remove work/ and everything but TASK.md (git branches are kept)."""
    _, workspace, project, name = resolve(name, project_opt)
    with workspace_lock(workspace.root):
        outcome = close_task(workspace, Graph.load(workspace), project, name, confirm=confirmer(force), status=status)
    warn_all(outcome.warnings)


# Workspace operations (§7)


@task.command()
@click.argument("name")
@PROJECT_OPTION
@click.option("--status", type=click.Choice(["done", "cancelled"]), help="With -f on an open task: set before closing.")
@click.option("-f", "--force", is_flag=True, help="Close an open task first, skipping its confirmations.")
def archive(name, project_opt, status, force):
    """Move a closed task to the project's .archive/."""
    _, workspace, project, name = resolve(name, project_opt)
    with workspace_lock(workspace.root):
        outcome = archive_task(workspace, Graph.load(workspace), project, name,
                               confirm=confirmer(force), force=force, status=status)
    warn_all(outcome.warnings)


@task.command()
@click.argument("name")
@PROJECT_OPTION
def restore(name, project_opt):
    """Bring an archived task back (it stays closed)."""
    _, workspace, project, name = resolve(name, project_opt)
    with workspace_lock(workspace.root):
        warn_all(restore_task(workspace, project, name).warnings)


@task.command()
@click.argument("name")
@PROJECT_OPTION
@click.option("-f", "--force", is_flag=True, help="Don't ask for confirmation.")
def delete(name, project_opt, force):
    """Delete a task permanently; references to it are removed."""
    _, workspace, project, name = resolve(name, project_opt)
    with workspace_lock(workspace.root):
        warn_all(delete_task(workspace, project, name, confirm=confirmer(force)).warnings)


@task.command()
@click.argument("name")
@click.argument("new_name")
@PROJECT_OPTION
def rename(name, new_name, project_opt):
    """Rename a closed or archived task (references and its git branch follow)."""
    config, workspace, project, name = resolve(name, project_opt)
    with workspace_lock(workspace.root):
        warn_all(rename_task(workspace, project, name, new_name, bases=config.bases).warnings)


@task.command()
@click.argument("name")
@click.argument("destination", metavar="PROJECT")
@PROJECT_OPTION
def move(name, destination, project_opt):
    """Move a closed or archived task to another project (references follow)."""
    _, workspace, project, name = resolve(name, project_opt)
    with workspace_lock(workspace.root):
        warn_all(move_task(workspace, project, name, destination).warnings)


# Sections (§9)


def _section_file(name: str, project_opt: str | None, writing: bool):
    _, workspace, project, name = resolve(name, project_opt)
    path = _task_file(workspace, project, name)
    if writing and path != workspace.live_task_file(project, name):
        raise ChreosError(f"task '{project}/{name}' is archived; restore it first")
    return workspace, project, path


@task.group(context_settings=CONTEXT_SETTINGS)
def description():
    """Show or change a task's ## Description section."""


@description.command(name="show")
@click.argument("name")
@PROJECT_OPTION
def description_show(name, project_opt):
    """Print the section content."""
    _, _, path = _section_file(name, project_opt, writing=False)
    content = read_section(load(path).body, "Description")
    if content:
        click.echo(content)


def _write_description(name, project_opt, text, append):
    content = validate_description(read_text_argument(text, sys.stdin))
    workspace, _, path = _section_file(name, project_opt, writing=True)
    write = append_text if append else write_section
    modify_body(workspace, path, lambda body: write(body, "Description", content, TASK_SECTIONS))


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


def _list_section(group_name, heading, kind, option_names, metavar, help_text, to_json, validate=None):
    """Build a `show|append|replace` group for a list section."""

    @task.group(name=group_name, context_settings=CONTEXT_SETTINGS, help=f"Show or change a task's ## {heading} section.")
    def group():
        pass

    @group.command(name="show")
    @click.argument("name")
    @PROJECT_OPTION
    @JSON_OPTION
    def show_(name, project_opt, as_json):
        """Print the list."""
        config = load_context()[0]
        _, _, path = _section_file(name, project_opt, writing=False)
        body = load(path).body
        items = read_items(body, heading, kind)
        if wants_json(as_json, config.output_format):
            emit_json([to_json(item) for item in items])
        else:
            for item in items:
                box = ("[x] " if item.checked else "[ ] ") if kind is ListKind.CHECKLIST else ""
                click.echo(f"- {box}{item.text}")

    def writer(replace: bool):
        @click.argument("name")
        @click.option(*option_names, "values", multiple=True, required=True, metavar=metavar, help=help_text)
        @PROJECT_OPTION
        def command(name, values, project_opt):
            workspace, project, path = _section_file(name, project_opt, writing=True)
            if validate:
                for value in values:
                    validate(workspace, project, value)
            write = replace_items if replace else append_items
            modify_body(workspace, path, lambda body: write(body, heading, kind, values, TASK_SECTIONS))

        command.__doc__ = "Replace the whole list." if replace else "Add items at the end of the list."
        return command

    group.command(name="append")(writer(replace=False))
    group.command(name="replace")(writer(replace=True))
    return group


def _ref_kind(text: str):
    try:
        return classify_reference(text)
    except ChreosError:
        return None


ac = _list_section(
    "ac", "Acceptance criteria", ListKind.CHECKLIST, ("-a", "--ac", "--acceptance-criteria"), "TEXT",
    "A criterion; repeatable. replace writes them all unchecked.",
    lambda item: {"text": item.text, "checked": item.checked},
)
refs = _list_section(
    "refs", "References", ListKind.BULLETS, ("-r", "--ref"), "TEXT",
    "A Markdown link, a URL or an item reference; repeatable.",
    lambda item: {"text": item.text, "kind": _ref_kind(item.text)},
    validate=lambda workspace, project, value: validate_reference(workspace, project, value),
)
notes = _list_section(
    "notes", "Notes", ListKind.BULLETS, ("-N", "--note"), "TEXT", "A note; repeatable.",
    lambda item: item.text,
)
