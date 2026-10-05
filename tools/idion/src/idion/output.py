"""Output shapes. The JSON shapes are a stable contract for scripts and agents (design §6)."""

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime

from idion.files import LoadedFile
from idion.listing import FOLDER, Entry
from idion.tree import ERROR, Finding


def jsonable(value: object) -> object:
    """Convert loaded YAML values to plain JSON values (copied from chreos)."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [jsonable(item) for item in value]
    return value


def show_entry(loaded: LoadedFile) -> dict:
    """`show --json`: a broken file has `frontmatter: null` and its whole text as `body`."""
    return {
        "id": str(loaded.id),
        "path": str(loaded.path),
        "frontmatter": jsonable(loaded.doc.meta) if loaded.doc else None,
        "body": loaded.doc.body if loaded.doc else loaded.text,
        "problems": list(loaded.problems),
    }


def list_line(entry: Entry) -> str:
    """`<id> — <description>`, with the file count on collapsed folders (§5)."""
    if entry.description is not None:
        description = entry.description
    else:
        description = "(no description)" if entry.kind == FOLDER else "(invalid description)"
    line = f"{entry.id} — {description}"
    if entry.files is not None:
        line += f" ({entry.files} {'file' if entry.files == 1 else 'files'})"
    return line


def list_entry(entry: Entry) -> dict:
    """One `list --json` entry; `files` only on collapsed folders (§6)."""
    data = {"id": str(entry.id), "kind": entry.kind, "description": entry.description, "path": str(entry.path)}
    if entry.files is not None:
        data["files"] = entry.files
    return data


def sorted_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Errors first, then by path (§7)."""
    return sorted(findings, key=lambda finding: (finding.severity != ERROR, finding.path))


def check_report(findings: Iterable[Finding]) -> dict:
    """`check --json` (§7)."""
    ordered = sorted_findings(findings)
    errors = sum(1 for finding in ordered if finding.severity == ERROR)
    return {
        "findings": [
            {"severity": f.severity, "path": str(f.path), "id": f.id, "message": f.message} for f in ordered
        ],
        "errors": errors,
        "warnings": len(ordered) - errors,
    }


def table(rows: Sequence[Sequence[str]]) -> list[str]:
    """Left-aligned columns separated by two spaces; the last column is not padded (copied from chreos)."""
    if not rows:
        return []
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]) - 1)]
    return ["  ".join([*(cell.ljust(width) for cell, width in zip(row, widths)), row[-1]]) for row in rows]
