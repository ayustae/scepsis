"""`idion folder`: folder descriptions in `_index.md` (design §5, §6)."""

import click

from idion.cli_support import CONTEXT_SETTINGS, require_root
from idion.commands.files import emit_loaded
from idion.files import describe_folder, load_index
from idion.identifiers import parse_folder_id
from idion.schema import validate_description


@click.group(context_settings=CONTEXT_SETTINGS)
def folder():
    """Describe folders and show their descriptions."""


@folder.command(context_settings=CONTEXT_SETTINGS)
@click.argument("identifier", metavar="FOLDER")
@click.option("-d", "--description", required=True, metavar="DESC", help="One-line summary of the folder's contents.")
def describe(identifier, description):
    """Set the description of FOLDER, such as teams/, and print its _index.md path."""
    root = require_root()
    folder_id = parse_folder_id(identifier)
    click.echo(describe_folder(root, folder_id, validate_description(description)))


@folder.command(context_settings=CONTEXT_SETTINGS)
@click.argument("identifier", metavar="FOLDER")
@click.option("--json", "as_json", is_flag=True, help="Print a JSON object.")
def show(identifier, as_json):
    """Print the description file of FOLDER."""
    emit_loaded(load_index(require_root(), parse_folder_id(identifier)), as_json)
