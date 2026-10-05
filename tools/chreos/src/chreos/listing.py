"""Filtering and sorting for the `list` commands (design §12 conventions)."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime

from chreos.items import LoadedItem

SORT_KEYS = ("name", "created", "updated", "status")
TASK_SORT_KEYS = (*SORT_KEYS, "priority", "due")
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@dataclass
class Filters:
    name: str | None = None
    title: str | None = None
    summary: str | None = None
    search: str | None = None
    labels: list[str] = field(default_factory=list)
    statuses: set[str] | None = None  # None: every status


def _contains(value: object, needle: str | None) -> bool:
    return needle is None or (isinstance(value, str) and needle.lower() in value.lower())


def _has_label(labels: list, wanted: str) -> bool:
    wanted = wanted.lower()
    if "=" in wanted:
        return wanted in labels
    return any(label == wanted or label.startswith(f"{wanted}=") for label in labels)


def matches(item: LoadedItem, filters: Filters) -> bool:
    meta = item.doc.meta
    labels = [label for label in meta.get("labels") or [] if isinstance(label, str)]
    return (
        _contains(item.name, filters.name)
        and _contains(meta.get("title"), filters.title)
        and _contains(meta.get("summary"), filters.summary)
        and _contains(item.doc.body, filters.search)
        and all(_has_label(labels, wanted) for wanted in filters.labels)
        and (filters.statuses is None or meta.get("status") in filters.statuses)
    )


def filter_items(
    items: Iterable[LoadedItem], filters: Filters, extra: Callable[[LoadedItem], bool] | None = None
) -> list[LoadedItem]:
    return [item for item in items if matches(item, filters) and (extra is None or extra(item))]


def _timestamp(value: object) -> datetime | None:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    return value if isinstance(value, datetime) and value.utcoffset() is not None else None


def sort_items(items: Iterable[LoadedItem], key: str) -> list[LoadedItem]:
    """Sort by `key`; items missing the value go last; ties by project, then name."""
    by_name = sorted(items, key=lambda item: (item.project, item.name))
    if key == "name":
        return by_name
    if key in ("created", "updated"):
        def sort_key(item):
            value = _timestamp(item.doc.meta.get(key))
            return (value is None, value.timestamp() if value else 0)
    elif key == "priority":
        def sort_key(item):
            rank = PRIORITY_ORDER.get(item.doc.meta.get("priority"))
            return (rank is None, rank or 0)
    elif key == "due":
        def sort_key(item):
            value = item.doc.meta.get("due")
            valid = isinstance(value, date) and not isinstance(value, datetime)
            return (not valid, value.toordinal() if valid else 0)
    else:
        def sort_key(item):
            value = item.doc.meta.get(key)
            return (not isinstance(value, str), value if isinstance(value, str) else "")
    return sorted(by_name, key=sort_key)
