"""Value sets and validation of single field values (design §3, §5, §10, §11.1)."""

import re
from collections.abc import Callable, Iterable
from datetime import date
from enum import StrEnum

from chreos.errors import ChreosError

NAME_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
NAME_MAX_LENGTH = 64
LABEL_PATTERN = re.compile(r"[a-z0-9_-]+(=[^\s,=]+)?")
DUE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
NONE = "none"


class Kind(StrEnum):
    PROJECT = "project"
    TASK = "task"
    DECISION = "decision"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class DecisionStatus(StrEnum):
    PENDING = "pending"
    DECIDED = "decided"


class TaskStatus(StrEnum):
    NEW = "new"
    TODO = "todo"
    IN_PROGRESS = "in-progress"
    ON_HOLD = "on-hold"
    DONE = "done"
    CANCELLED = "cancelled"


class Phase(StrEnum):
    CLOSED = "closed"
    OPEN = "open"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SourceType(StrEnum):
    GIT = "git"
    LOCAL = "local"


ALLOWED_STATUSES = {
    Phase.CLOSED: {TaskStatus.NEW, TaskStatus.DONE, TaskStatus.CANCELLED},
    Phase.OPEN: {
        TaskStatus.TODO,
        TaskStatus.ON_HOLD,
        TaskStatus.IN_PROGRESS,
        TaskStatus.DONE,
        TaskStatus.CANCELLED,
    },
}


def is_valid_name(name: object) -> bool:
    return (
        isinstance(name, str)
        and len(name) <= NAME_MAX_LENGTH
        and NAME_PATTERN.fullmatch(name) is not None
    )


def validate_name(name: object) -> str:
    """Return `name` if valid (§5); never rewrite it."""
    if not is_valid_name(name):
        raise ChreosError(
            f"invalid name {name!r}: use lowercase letters and digits in segments "
            f"separated by single hyphens, at most {NAME_MAX_LENGTH} characters"
        )
    return name


def normalize_labels(labels: Iterable[object]) -> list[str]:
    """Lowercase, validate and deduplicate labels, keeping first-seen order (§3.5)."""
    result: list[str] = []
    for label in labels:
        normalized = label.lower() if isinstance(label, str) else None
        if normalized is None or not LABEL_PATTERN.fullmatch(normalized):
            raise ChreosError(
                f"invalid label {label!r}: use 'key' or 'key=value'; key from "
                "[a-z0-9_-], value non-empty without whitespace, commas or '='"
            )
        if normalized not in result:
            result.append(normalized)
    return result


def check_status_for_phase(phase: Phase, status: TaskStatus) -> None:
    """Refuse a task status that isn't allowed in `phase` (§11.1)."""
    if status not in ALLOWED_STATUSES[phase]:
        allowed = ", ".join(sorted(ALLOWED_STATUSES[phase]))
        raise ChreosError(
            f"status '{status}' is not allowed in phase '{phase}' (allowed: {allowed}); "
            "use 'task open' or 'task close' to change the phase"
        )


def parse_priority(value: str) -> Priority:
    try:
        return Priority(value)
    except ValueError:
        allowed = ", ".join(Priority)
        raise ChreosError(f"invalid priority {value!r} (allowed: {allowed})") from None


def parse_due(value: str) -> date:
    try:
        if not DUE_PATTERN.fullmatch(value):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError:
        raise ChreosError(f"invalid due date {value!r}: use YYYY-MM-DD") from None


def parse_assignee(value: str) -> str:
    stripped = value.strip()
    if not stripped or "\n" in stripped or "\r" in stripped:
        raise ChreosError(f"invalid assignee {value!r}: use non-empty single-line text")
    return stripped


def parse_optional[T](value: str, parser: Callable[[str], T]) -> T | None:
    """Parse an option value where the literal `none` clears the field (§12)."""
    return None if value == NONE else parser(value)
