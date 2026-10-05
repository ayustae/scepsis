"""Output shapes. The JSON shapes are a stable contract for scripts and agents (§12)."""

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from enum import Enum

from chreos.items import LoadedItem
from chreos.timestamps import format_timestamp


def jsonable(value: object) -> object:
    """Convert loaded YAML values to plain JSON values."""
    if isinstance(value, datetime):
        return format_timestamp(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [jsonable(item) for item in value]
    return value


def list_entry(item: LoadedItem) -> dict:
    """One `list --json` entry: the frontmatter fields plus `path`."""
    return {**jsonable(item.doc.meta), "path": str(item.path)}


def show_entry(item: LoadedItem) -> dict:
    """`show --json`: frontmatter, body and path (tasks and decisions add more)."""
    return {"frontmatter": jsonable(item.doc.meta), "body": item.doc.body, "path": str(item.path)}


def table(rows: Sequence[Sequence[str]]) -> list[str]:
    """Left-aligned columns separated by two spaces; the last column is not padded."""
    if not rows:
        return []
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]) - 1)]
    return ["  ".join([*(cell.ljust(width) for cell, width in zip(row, widths)), row[-1]]) for row in rows]
