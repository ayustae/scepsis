"""`idion search`: find context files by identifier, description or body text."""

import click

from idion.cli_support import CONTEXT_SETTINGS, emit_json, require_root, warn
from idion.errors import IdionError
from idion.identifiers import parse_folder_id, resolve
from idion.listing import findings_under
from idion.output import search_entry, search_lines
from idion.search import search_tree
from idion.tree import scan


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("text")
@click.argument("prefix", metavar="[PREFIX]", default="/")
@click.option("--json", "as_json", is_flag=True, help="Print a JSON array.")
def search(text, prefix, as_json):
    """List context files whose id, description or body contains TEXT (any case), with the matching lines."""
    if not text.strip():
        raise IdionError("the search text is empty")
    root = require_root()
    folder_id = parse_folder_id(prefix)
    folder_path = resolve(root, folder_id)
    if not folder_path.is_dir():
        raise IdionError(f"no folder '{folder_id}' ({folder_path})")
    tree = scan(root)
    matches = search_tree(tree, folder_id, text)
    problems = len(findings_under(tree, folder_path))
    if problems:
        warn(f"{problems} {'problem' if problems == 1 else 'problems'} in the context tree; run 'idion check'")
    if as_json:
        emit_json([search_entry(match) for match in matches])
        return
    for match in matches:
        for line in search_lines(match):
            click.echo(line)
