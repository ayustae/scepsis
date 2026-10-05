"""Validation of the `description` field (design §3).

`validate_description` checks CLI input and raises; `description_problems`
checks a loaded frontmatter and returns every problem. Unknown keys are allowed.
"""

import re
from collections.abc import Mapping

from idion.errors import IdionError

DESCRIPTION = "description"
DESCRIPTION_MAX_LENGTH = 200
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _problem(value: object) -> str | None:
    if not isinstance(value, str):
        return "description must be text"
    if not value:
        return "description is empty"
    if CONTROL.search(value):
        return "description must be a single line without control characters"
    if len(value) > DESCRIPTION_MAX_LENGTH:
        return f"description must be at most {DESCRIPTION_MAX_LENGTH} characters"
    return None


def validate_description(value: object) -> str:
    """Return `value` stripped of surrounding whitespace, or raise if it isn't valid."""
    if isinstance(value, str):
        value = value.strip()
    problem = _problem(value)
    if problem:
        raise IdionError(f"invalid description: {problem}")
    return value


def description_problems(meta: Mapping) -> list[str]:
    if DESCRIPTION not in meta:
        return ["description is missing"]
    problem = _problem(meta[DESCRIPTION])
    return [problem] if problem else []
