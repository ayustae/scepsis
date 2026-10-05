"""`idion init` (design §2, §6)."""

import click

from idion.cli_support import CONTEXT_SETTINGS, check_root_path
from idion.paths import context_root

ROOT_MODE = 0o700


@click.command(context_settings=CONTEXT_SETTINGS)
def init():
    """Create the context tree in ~/.scepsis/context/."""
    root = context_root()
    check_root_path(root)
    if root.is_dir():
        click.echo(f"{root} already exists")
        return
    root.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir(mode=ROOT_MODE)
    click.echo(f"Created {root}")
