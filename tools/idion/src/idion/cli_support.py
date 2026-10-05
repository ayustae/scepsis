"""Plumbing shared by all commands: errors and the context root (design §6)."""

import json
import sys
from collections.abc import Callable
from pathlib import Path

import click

from idion.errors import IdionError
from idion.paths import context_root

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


class IdionGroup(click.Group):
    """Root group: user and validation errors exit with 1, usage errors with 2 (§6)."""

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except IdionError as error:
            raise click.ClickException(str(error)) from error
        except OSError as error:
            target = f": {error.filename}" if error.filename else ""
            raise click.ClickException(f"{error.strerror or error}{target}") from error


def check_root_path(root: Path) -> None:
    if root.exists() and not root.is_dir():
        raise IdionError(f"{root} is not a folder: move it away, then run 'idion init'")


def require_root() -> Path:
    """The context root; fails with a hint when `idion init` hasn't run (§6)."""
    root = context_root()
    check_root_path(root)
    if not root.is_dir():
        raise IdionError(f"no context tree at {root}: run 'idion init' first")
    return root


def warn(message: str) -> None:
    click.echo(f"warning: {message}", err=True)


def emit_json(data: object) -> None:
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


def is_interactive() -> bool:
    return sys.stdin.isatty()


def confirmer(force: bool) -> Callable[[str], bool]:
    """`-f` says yes; otherwise ask on a terminal and fail without one (copied from chreos)."""

    def confirm(message: str) -> bool:
        if force:
            return True
        if not is_interactive():
            raise IdionError(f"confirmation required: run in a terminal or pass -f\n{message}")
        return click.confirm(message, default=False)

    return confirm
