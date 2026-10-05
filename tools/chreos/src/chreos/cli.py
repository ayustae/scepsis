"""Command line entry point."""

import click

from chreos.cli_support import CONTEXT_SETTINGS, ChreosGroup
from chreos.commands import check, decision, project, setup, task


@click.group(cls=ChreosGroup, context_settings=CONTEXT_SETTINGS)
@click.version_option(
    None,
    "-V",
    "--version",
    package_name="chreos",
    prog_name="chreos",
    message="%(prog)s %(version)s",
)
def main():
    """Manage projects, tasks and decisions in a local Scepsis workspace."""


main.add_command(setup.init)
main.add_command(setup.config)
main.add_command(project.project)
main.add_command(task.task)
main.add_command(decision.decision)
main.add_command(check.check)
