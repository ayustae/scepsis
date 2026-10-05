"""Confirmations before accepting work (design §10).

Core code never prompts. Callers pass a `confirm(message) -> bool` callback:
the CLI asks on a terminal (and fails without one), `-f` always says yes.
"""

from collections.abc import Callable, Sequence

from chreos.errors import ChreosError
from chreos.graph import DependencyStatus
from chreos.lists import ListKind, read_items

Confirm = Callable[[str], bool]


def _unsatisfied(statuses: Sequence[DependencyStatus]) -> list[str]:
    return [
        f"{status.ref} ({status.status or 'unresolved'})"
        for status in statuses
        if not status.satisfied
    ]


def done_message(body: str, statuses: Sequence[DependencyStatus]) -> str | None:
    """What to confirm before a task becomes `done`, or None."""
    unchecked = sum(
        1 for item in read_items(body, "Acceptance criteria", ListKind.CHECKLIST) if not item.checked
    )
    unsatisfied = _unsatisfied(statuses)
    if not unchecked and not unsatisfied:
        return None
    reasons = []
    if unchecked:
        noun = "criterion" if unchecked == 1 else "criteria"
        reasons.append(f"{unchecked} unchecked acceptance {noun}")
    if unsatisfied:
        reasons.append(f"unsatisfied dependencies: {', '.join(unsatisfied)}")
    return f"Mark the task as done with {' and '.join(reasons)}?"


def decided_message(statuses: Sequence[DependencyStatus]) -> str | None:
    unsatisfied = _unsatisfied(statuses)
    if not unsatisfied:
        return None
    return f"Mark the decision as decided with unsatisfied dependencies: {', '.join(unsatisfied)}?"


def require(message: str | None, confirm: Confirm) -> None:
    if message is not None and not confirm(message):
        raise ChreosError("cancelled")
