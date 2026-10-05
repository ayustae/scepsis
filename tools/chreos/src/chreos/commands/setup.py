"""`chreos init` and `chreos config` (design §12.1, §13)."""

import click

from chreos import cli_support
from chreos.cli_support import CONTEXT_SETTINGS, confirmer, emit_json, wants_json, warn
from chreos.config import config_path, get_value, load_config, render_new_config, set_value, set_values
from chreos.confirmations import require
from chreos.fileio import atomic_write
from chreos.lock import workspace_lock
from chreos.model import validate_name
from chreos.paths import parse_path
from chreos.projects import create_project
from chreos.workspace import Workspace

DEFAULT_WORKSPACE = "~/scepsis-workspace"


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option("--workspace-path", metavar="PATH", help="Workspace folder (prompted if omitted on a terminal).")
@click.option("--default-project", default="default", show_default=True, metavar="NAME", help="Default project; created if missing.")
@click.option("--source-git-path", metavar="PATH", help="Base folder for relative git sources.")
@click.option("--source-local-path", metavar="PATH", help="Base folder for relative local sources.")
@click.option("-f", "--force", is_flag=True, help="Overwrite an existing config.toml without asking.")
def init(workspace_path, default_project, source_git_path, source_local_path, force):
    """Create the configuration, the workspace and its default project."""
    if workspace_path is None:
        if not cli_support.is_interactive():
            raise click.UsageError("--workspace-path is required when not running in a terminal")
        workspace_path = click.prompt("Workspace path", default=DEFAULT_WORKSPACE)
    root = parse_path(workspace_path)
    validate_name(default_project)
    bases = {key: value for key, value in (("git", source_git_path), ("local", source_local_path)) if value}
    resolved_bases = {key: parse_path(value) for key, value in bases.items()}

    path = config_path()
    if path.exists():
        require(f"Overwrite the existing configuration at {path}?", confirmer(force))

    root.mkdir(parents=True, exist_ok=True)
    workspace = Workspace(root)
    with workspace_lock(root):
        if not workspace.project_exists(default_project):
            create_project(workspace, default_project)
            click.echo(f"Created project '{default_project}' in {root}")
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(
        path,
        render_new_config(
            workspace_path, default_project, git_path=source_git_path, local_path=source_local_path
        ),
    )
    click.echo(f"Wrote {path}")
    for kind, folder in resolved_bases.items():
        if not folder.is_dir():
            warn(f"the {kind} source base folder {folder} does not exist yet")


@click.group(context_settings=CONTEXT_SETTINGS)
def config():
    """Show or change the configuration (~/.scepsis/config.toml)."""


def _output_format() -> str:
    return load_config().output_format


@config.command()
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
def show(as_json):
    """Show the configured keys."""
    values = set_values()
    if wants_json(as_json, _output_format()):
        nested: dict = {}
        for key, value in values.items():
            section, field = key.split(".")
            nested.setdefault(section, {})[field] = value
        emit_json(nested)
    else:
        for key, value in values.items():
            click.echo(f"{key} = {value}")


@config.command()
@click.argument("key")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
def get(key, as_json):
    """Print one value. KEY is dotted, e.g. source.git_path."""
    value = get_value(key)
    if wants_json(as_json, _output_format()):
        emit_json(value)
    elif value is not None:
        click.echo(value)


@config.command(name="set")
@click.argument("key")
@click.argument("value")
def set_(key, value):
    """Set one value; `none` removes an optional key."""
    set_value(key, value)
