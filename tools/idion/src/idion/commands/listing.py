"""`idion list` (design §5, §6)."""

import click

from idion.cli_support import CONTEXT_SETTINGS, emit_json, require_root, warn
from idion.errors import IdionError
from idion.identifiers import parse_folder_id, resolve
from idion.listing import build_listing, findings_under
from idion.output import list_entry, list_line
from idion.tree import scan


@click.command(name="list", context_settings=CONTEXT_SETTINGS)
@click.argument("prefix", metavar="[PREFIX]", default="/")
@click.option("--depth", type=click.IntRange(min=1), metavar="N", help="Collapse everything below N levels into folders.")
@click.option("--folders", is_flag=True, help="Also list described folders that are not collapsed.")
@click.option("-S", "--search", metavar="TEXT", help="Only files whose id or description contains TEXT (any case).")
@click.option("--json", "as_json", is_flag=True, help="Print a JSON array.")
def list_(prefix, depth, folders, search, as_json):
    """List context files as '<id> — <description>' (PREFIX: a folder such as teams/)."""
    root = require_root()
    folder_id = parse_folder_id(prefix)
    folder_path = resolve(root, folder_id)
    if not folder_path.is_dir():
        raise IdionError(f"no folder '{folder_id}' ({folder_path})")
    tree = scan(root)
    entries = build_listing(tree, folder_id, depth=depth, folders=folders, search=search)
    problems = len(findings_under(tree, folder_path))
    if problems:
        warn(f"{problems} {'problem' if problems == 1 else 'problems'} in the context tree; run 'idion check'")
    if as_json:
        emit_json([list_entry(entry) for entry in entries])
        return
    for entry in entries:
        click.echo(list_line(entry))
