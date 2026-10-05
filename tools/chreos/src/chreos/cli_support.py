"""Plumbing shared by all commands: errors, confirmations, output."""

import json
import sys

import click

from chreos.confirmations import Confirm
from chreos.errors import ChreosError

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


class ChreosGroup(click.Group):
    """Root group: user and validation errors exit with 1, usage errors with 2 (§12)."""

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except ChreosError as error:
            raise click.ClickException(str(error)) from error
        except OSError as error:
            target = f": {error.filename}" if error.filename else ""
            raise click.ClickException(f"{error.strerror or error}{target}") from error


def is_interactive() -> bool:
    return sys.stdin.isatty()


def confirmer(force: bool) -> Confirm:
    """`-f` says yes; otherwise ask on a terminal and fail without one (§12)."""

    def confirm(message: str) -> bool:
        if force:
            return True
        if not is_interactive():
            raise ChreosError(f"confirmation required: run in a terminal or pass -f\n{message}")
        return click.confirm(message, default=False)

    return confirm


def warn(message: str) -> None:
    click.echo(f"warning: {message}", err=True)


def wants_json(flag: bool, output_format: str) -> bool:
    return flag or output_format == "json"


def emit_json(data: object) -> None:
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))
