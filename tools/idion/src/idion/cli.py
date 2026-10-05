"""Command line entry point."""

import click

from idion.cli_support import CONTEXT_SETTINGS, IdionGroup
from idion.commands import check, files, folders, listing, setup


@click.group(cls=IdionGroup, context_settings=CONTEXT_SETTINGS)
@click.version_option(
    None,
    "-V",
    "--version",
    package_name="idion",
    prog_name="idion",
    message="%(prog)s %(version)s",
)
def main():
    """Manage the user context files in ~/.scepsis/context/."""


main.add_command(setup.init)
main.add_command(files.create)
main.add_command(files.show)
main.add_command(files.update)
main.add_command(files.append)
main.add_command(files.edit)
main.add_command(files.move)
main.add_command(files.delete)
main.add_command(listing.list_)
main.add_command(folders.folder)
main.add_command(check.check)
