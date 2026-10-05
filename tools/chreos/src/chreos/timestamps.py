"""Timestamps for `created`, `updated` and `archived` (design §3.1)."""

from datetime import datetime


def now() -> datetime:
    """Current local time with its UTC offset, to the second."""
    return datetime.now().astimezone().replace(microsecond=0)


def format_timestamp(value: datetime) -> str:
    """ISO 8601 with a `T` separator and UTC offset, e.g. `2026-09-21T10:00:00+02:00`."""
    return value.isoformat(timespec="seconds")
