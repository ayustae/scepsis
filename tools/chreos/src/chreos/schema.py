"""Validation of a whole frontmatter mapping per item type (design §3, §11.1).

Returns every problem found instead of raising, so `check` and `edit` can
report them all. Unknown keys are allowed.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from chreos.errors import ChreosError
from chreos.model import (
    DecisionStatus,
    Kind,
    Phase,
    Priority,
    ProjectStatus,
    SourceType,
    TaskStatus,
    check_status_for_phase,
    normalize_labels,
    parse_assignee,
    validate_name,
)

STATUSES: dict[Kind, type[StrEnum]] = {
    Kind.PROJECT: ProjectStatus,
    Kind.TASK: TaskStatus,
    Kind.DECISION: DecisionStatus,
}


@dataclass(frozen=True)
class Problem:
    field: str
    message: str

    def __str__(self) -> str:
        return f"{self.field}: {self.message}"


class _Invalid(Exception):
    pass


def _name(value):
    try:
        validate_name(value)
    except ChreosError as error:
        raise _Invalid(str(error)) from None


def _title(value):
    if not isinstance(value, str) or not value.strip():
        raise _Invalid("must be non-empty text")


def _optional_text(value):
    if value is not None and not isinstance(value, str):
        raise _Invalid("must be text or null")


def _enum(enum: type[StrEnum]) -> Callable[[object], None]:
    def check(value):
        if value not in {member.value for member in enum}:
            raise _Invalid(f"invalid value {value!r} (allowed: {', '.join(enum)})")

    return check


def _optional(check: Callable[[object], None]) -> Callable[[object], None]:
    def wrapped(value):
        if value is not None:
            check(value)

    return wrapped


def _timestamp(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            raise _Invalid(f"invalid timestamp {value!r}") from None
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise _Invalid("must be an ISO 8601 timestamp with UTC offset")


def _labels(value):
    if not isinstance(value, list):
        raise _Invalid("must be a list")
    try:
        normalized = normalize_labels(value)
    except ChreosError as error:
        raise _Invalid(str(error)) from None
    if normalized != value:
        raise _Invalid("labels must be lowercase and unique")


def _string_list(value):
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise _Invalid("must be a list of strings")


def _due(value):
    if isinstance(value, datetime) or not isinstance(value, date):
        raise _Invalid("must be a date (YYYY-MM-DD)")


def _assignee(value):
    try:
        if not isinstance(value, str):
            raise ChreosError("must be text")
        if parse_assignee(value) != value:
            raise ChreosError("must not have surrounding whitespace")
    except ChreosError as error:
        raise _Invalid(str(error)) from None


def _source(value):
    if not isinstance(value, Mapping):
        raise _Invalid("must be null or a mapping with 'type' and 'path'")
    if set(value) != {"type", "path"}:
        raise _Invalid("must have exactly the keys 'type' and 'path'")
    _enum(SourceType)(value["type"])
    if not isinstance(value["path"], str) or not value["path"]:
        raise _Invalid("'path' must be non-empty text")


# field -> (required, check)
_COMMON = {
    "name": (True, _name),
    "title": (True, _title),
    "summary": (False, _optional_text),
    "labels": (False, _labels),
    "created": (True, _timestamp),
    "updated": (True, _timestamp),
}

_FIELDS: dict[Kind, dict] = {
    Kind.PROJECT: {},
    Kind.TASK: {
        "project": (True, _name),
        "phase": (True, _enum(Phase)),
        "source": (False, _optional(_source)),
        "priority": (False, _optional(_enum(Priority))),
        "due": (False, _optional(_due)),
        "assignee": (False, _optional(_assignee)),
        "dependencies": (False, _string_list),
        "archived": (False, _timestamp),
    },
    Kind.DECISION: {
        "project": (True, _name),
        "dependencies": (False, _string_list),
    },
}


def validate(kind: Kind, meta: Mapping) -> list[Problem]:
    fields = {**_COMMON, "status": (True, _enum(STATUSES[kind])), **_FIELDS[kind]}
    problems = []
    for field, (required, check) in fields.items():
        if field not in meta:
            if required:
                problems.append(Problem(field, "missing required field"))
            continue
        try:
            check(meta[field])
        except _Invalid as error:
            problems.append(Problem(field, str(error)))
    if kind is Kind.TASK and not {p.field for p in problems} & {"phase", "status"}:
        try:
            check_status_for_phase(Phase(meta["phase"]), TaskStatus(meta["status"]))
        except ChreosError as error:
            problems.append(Problem("status", str(error)))
    return problems
