"""Commands on context files (design §6)."""

import sys

import click

from idion import cli_support
from idion.cli_support import CONTEXT_SETTINGS, confirmer, emit_json, require_root, warn
from idion.editing import edit_file
from idion.errors import IdionError
from idion.files import (
    LoadedFile,
    append_text,
    create_file,
    delete_entry,
    load_file,
    load_index,
    move_entry,
    update_description,
)
from idion.identifiers import parse_file_id, parse_identifier
from idion.inputs import read_append_text, read_body
from idion.output import show_entry
from idion.schema import validate_description


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("identifier", metavar="ID")
@click.option("-d", "--description", required=True, metavar="DESC", help="One-line summary of the contents.")
@click.option("-b", "--body", metavar="TEXT", help="Initial body; '-' reads standard input. Default: '# <name>'.")
@click.option("--body-file", metavar="PATH", help="Read the initial body from a file.")
def create(identifier, description, body, body_file):
    """Create the context file ID, such as teams/my-team, and print its path."""
    if body is not None and body_file is not None:
        raise click.UsageError("-b/--body and --body-file exclude each other")
    root = require_root()
    file_id = parse_file_id(identifier)
    description = validate_description(description)
    text = read_body(body, body_file, sys.stdin)
    click.echo(create_file(root, file_id, description, text))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("identifier", metavar="ID")
@click.option("--json", "as_json", is_flag=True, help="Print a JSON object.")
def show(identifier, as_json):
    """Print the context file ID."""
    emit_loaded(load_file(require_root(), parse_file_id(identifier)), as_json)


def emit_loaded(loaded: LoadedFile, as_json: bool) -> None:
    """`show` output: the raw text with problems as warnings, or the JSON object."""
    if as_json:
        emit_json(show_entry(loaded))
        return
    for problem in loaded.problems:
        warn(problem)
    click.echo(loaded.text, nl=False)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("identifier", metavar="ID")
@click.option("-d", "--description", required=True, metavar="DESC", help="The new one-line summary.")
def update(identifier, description):
    """Change the description of the context file ID and print its path."""
    root = require_root()
    file_id = parse_file_id(identifier)
    click.echo(update_description(root, file_id, validate_description(description)))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("identifier", metavar="ID")
@click.option("-t", "--text", required=True, metavar="TEXT", help="Paragraph to append; '-' reads standard input.")
def append(identifier, text):
    """Append a paragraph to the body of the context file ID and print its path."""
    root = require_root()
    file_id = parse_file_id(identifier)
    path, problems = append_text(root, file_id, read_append_text(text, sys.stdin))
    for problem in problems:
        warn(problem)
    click.echo(path)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("identifier", metavar="ID")
def edit(identifier):
    """Open the context file ID (or a FOLDER/'s _index.md) in $VISUAL/$EDITOR, then validate it."""
    root = require_root()
    parsed = parse_identifier(identifier)
    loaded = load_index(root, parsed) if parsed.folder else load_file(root, parsed)
    if not cli_support.is_interactive():
        raise IdionError(f"edit needs a terminal; edit the file directly: {loaded.path}")
    result = edit_file(parsed, loaded.path)
    for problem in result.warnings:
        warn(problem)
    if result.errors:
        listing = "\n".join(f"  - {error}" for error in result.errors)
        raise IdionError(f"the edited file has validation errors:\n{listing}")


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("source", metavar="SRC")
@click.argument("destination", metavar="DST")
def move(source, destination):
    """Move the file or folder SRC to DST (a file to a file, a folder/ to a folder/) and print the new path."""
    root = require_root()
    click.echo(move_entry(root, parse_identifier(source), parse_identifier(destination)))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("identifier", metavar="ID")
@click.option("-f", "--force", is_flag=True, help="Don't ask; also needed to delete a folder that isn't empty.")
def delete(identifier, force):
    """Delete the context file ID, or a FOLDER/ with everything in it."""
    root = require_root()
    path = delete_entry(root, parse_identifier(identifier), confirmer(force), force)
    click.echo(f"Deleted {path}")
