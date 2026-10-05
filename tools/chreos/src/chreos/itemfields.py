"""Updates of the fields every item has: title, summary, labels, status (§3.1, §3.5, §8)."""

from collections.abc import Iterable
from enum import StrEnum

from chreos.body import sync_heading
from chreos.errors import ChreosError
from chreos.frontmatter import Document
from chreos.model import NONE, normalize_labels


def split_labels(values: Iterable[str]) -> list[str]:
    """Repeatable `-l` values; each may hold several comma-separated labels."""
    return normalize_labels(part for value in values for part in value.split(","))


def _single_line(value: str, field: str) -> str:
    if not value.strip() or "\n" in value or "\r" in value:
        raise ChreosError(f"the {field} must be non-empty single-line text")
    return value


def parse_status(value: str, statuses: type[StrEnum]) -> StrEnum:
    try:
        return statuses(value)
    except ValueError:
        raise ChreosError(f"invalid status {value!r} (allowed: {', '.join(statuses)})") from None


def update_common(
    doc: Document,
    *,
    title: str | None,
    summary: str | None,
    add_labels: Iterable[str],
    remove_labels: Iterable[str],
    status: str | None,
    statuses: type[StrEnum],
) -> tuple[bool, list[str]]:
    """Apply the common options; return (changed, warnings). The caller bumps `updated`."""
    meta = doc.meta
    new_title = _single_line(title, "title") if title is not None else meta.get("title")
    if summary is None:
        new_summary = meta.get("summary")
    else:
        new_summary = None if summary == NONE else _single_line(summary, "summary")
    new_status = parse_status(status, statuses) if status is not None else None
    added = split_labels(add_labels)
    removed = set(remove_labels)

    changed, warnings = False, []
    old_title, old_summary = meta.get("title"), meta.get("summary")
    if new_title != old_title or new_summary != old_summary:
        doc.body, warnings = sync_heading(doc.body, old_title, new_title, old_summary, new_summary)
        meta["title"], meta["summary"] = new_title, new_summary
        changed = True
    if new_status is not None and new_status != meta.get("status"):
        meta["status"] = new_status
        changed = True
    if added or removed:
        current = list(meta.get("labels") or [])
        labels = current + [label for label in added if label not in current]
        labels = [label for label in labels if label not in removed]  # removal wins
        if labels != current:
            if isinstance(meta.get("labels"), list):
                meta["labels"][:] = labels
            else:
                meta["labels"] = labels
            changed = True
    return changed, warnings
