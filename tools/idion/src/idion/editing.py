"""`edit`: open a file in $VISUAL/$EDITOR and validate it afterwards (design §6).

Adapted from chreos. The edit itself is never reverted or "fixed", and the CLI
never writes the file: idion has no field to bump, so a broken file is left
exactly as the editor saved it.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import click

from idion.errors import IdionError
from idion.files import load_path
from idion.identifiers import Identifier


@dataclass
class EditResult:
    changed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _launch(path: Path) -> None:
    click.edit(filename=str(path))


def edit_file(identifier: Identifier, path: Path, launch: Callable[[Path], None] = _launch) -> EditResult:
    before = _digest(path)
    launch(path)
    changed = _digest(path) != before
    loaded = load_path(identifier, path)
    if not changed:
        return EditResult(False, [], loaded.problems)
    if loaded.doc is None:
        raise IdionError(
            f"{loaded.problems[0]}\nThe file was left as saved: run 'idion edit {identifier}' again to fix it"
        )
    return EditResult(True, loaded.problems, [])
