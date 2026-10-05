"""`edit`: open an item in $VISUAL/$EDITOR and validate it afterwards (design §12).

The edit itself is never reverted or "fixed": a changed file that parses
gets `updated` bumped even if it has validation errors; one that doesn't
parse is left exactly as saved.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import click

from chreos.body import find_h1
from chreos.errors import ChreosError, FormatError
from chreos.frontmatter import Document, load, save
from chreos.lock import workspace_lock
from chreos.model import Kind
from chreos.schema import validate
from chreos.timestamps import now

Checks = Callable[[Document], tuple[list[str], list[str]]]


@dataclass
class EditResult:
    changed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def expected_caches(path: Path, kind: Kind) -> dict[str, str]:
    if kind is Kind.PROJECT:
        return {"name": path.parent.name}
    if path.name == "TASK.md":  # tasks/<name>/TASK.md
        return {"name": path.parent.name, "project": path.parents[2].name}
    return {"name": path.stem, "project": path.parents[1].name}  # .archive/ or decisions/


def file_checks(path: Path, kind: Kind, doc: Document) -> tuple[list[str], list[str]]:
    """Per-file checks shared with `check`: (errors, warnings)."""
    errors = [str(problem) for problem in validate(kind, doc.meta)]
    for key, expected in expected_caches(path, kind).items():
        value = doc.meta.get(key)
        if value is not None and value != expected:
            errors.append(f"{key}: '{value}' doesn't match the path ('{expected}'); 'chreos check --fix' repairs it")
    warnings = []
    lines = doc.body.splitlines()
    h1 = find_h1(lines)
    title = doc.meta.get("title")
    if isinstance(title, str) and (h1 is None or lines[h1] != f"# {title}"):
        warnings.append("the body's H1 differs from the title")
    return errors, warnings


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _launch(path: Path) -> None:
    click.edit(filename=str(path))


def edit_item(
    path: Path,
    kind: Kind,
    workspace_root: Path,
    *,
    extra_checks: Checks | None = None,
    launch: Callable[[Path], None] = _launch,
) -> EditResult:
    def checks(doc: Document) -> tuple[list[str], list[str]]:
        errors, warnings = file_checks(path, kind, doc)
        if extra_checks:
            more_errors, more_warnings = extra_checks(doc)
            errors, warnings = errors + more_errors, warnings + more_warnings
        return errors, warnings

    before = _digest(path)
    launch(path)
    if _digest(path) == before:
        try:
            errors, warnings = checks(load(path))
        except FormatError as error:
            errors, warnings = [str(error)], []
        return EditResult(False, [], errors + warnings)

    try:
        load(path)
    except FormatError as error:
        raise ChreosError(f"{error}\nThe file was left as saved: run 'edit' again to fix it") from None
    with workspace_lock(workspace_root):
        doc = load(path)
        doc.meta["updated"] = now()
        save(path, doc)
    errors, warnings = checks(doc)
    return EditResult(True, errors, warnings)
