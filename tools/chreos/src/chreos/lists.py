"""List sections (design §9): acceptance criteria, references and notes.

Only list-item lines of the section are read and written; any other line in
the section (prose, fenced code, nested content) is preserved.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from chreos.errors import ChreosError
from chreos.markdown import newline_of, unfenced
from chreos.sections import find_section, read_section, write_section


class ListKind(Enum):
    CHECKLIST = re.compile(r"- \[([ xX])\] (.*)")
    BULLETS = re.compile(r"- (.*)")


@dataclass(frozen=True)
class Item:
    text: str
    checked: bool | None = None


def _parse(kind: ListKind, line: str) -> Item | None:
    match = kind.value.fullmatch(line.rstrip("\r\n"))
    if match is None:
        return None
    if kind is ListKind.CHECKLIST:
        return Item(match.group(2), match.group(1) != " ")
    return Item(match.group(1))


def _format(kind: ListKind, text: str) -> str:
    return f"- [ ] {text}" if kind is ListKind.CHECKLIST else f"- {text}"


def _item_indices(lines: list[str], heading: str, kind: ListKind) -> list[int] | None:
    span = find_section(lines, heading)
    if span is None:
        return None
    return [
        index
        for index, line in unfenced(lines)
        if span.start <= index < span.end and _parse(kind, line)
    ]


def validate_items(values: Sequence[str]) -> list[str]:
    if not values:
        raise ChreosError("at least one value is required")
    result = []
    for value in values:
        stripped = value.strip()
        if not stripped or "\n" in stripped or "\r" in stripped:
            raise ChreosError(f"each value must be a non-empty single line: {value!r}")
        result.append(stripped)
    return result


def read_items(body: str, heading: str, kind: ListKind) -> list[Item]:
    lines = body.splitlines(keepends=True)
    return [_parse(kind, lines[index]) for index in _item_indices(lines, heading, kind) or []]


def _write_into_content(body, heading, kind, values, order) -> str:
    """For a section without items: add them after its content."""
    existing = read_section(body, heading) or ""
    items = "\n".join(_format(kind, value) for value in values)
    return write_section(body, heading, f"{existing}\n\n{items}" if existing else items, order)


def _insert(lines: list[str], index: int, kind: ListKind, values, newline: str) -> str:
    if index > 0 and not lines[index - 1].endswith(("\n", "\r")):
        lines[index - 1] += newline
    lines[index:index] = [_format(kind, value) + newline for value in values]
    return "".join(lines)


def append_items(body, heading, kind, values, order) -> str:
    values = validate_items(values)
    lines = body.splitlines(keepends=True)
    indices = _item_indices(lines, heading, kind)
    if not indices:
        return _write_into_content(body, heading, kind, values, order)
    return _insert(lines, indices[-1] + 1, kind, values, newline_of(body))


def replace_items(body, heading, kind, values, order) -> str:
    values = validate_items(values)
    lines = body.splitlines(keepends=True)
    indices = _item_indices(lines, heading, kind)
    if not indices:
        return _write_into_content(body, heading, kind, values, order)
    for index in reversed(indices):
        del lines[index]
    return _insert(lines, indices[0], kind, values, newline_of(body))


def map_items(body: str, heading: str, kind: ListKind, fn) -> str:
    """Replace each item's text with `fn(text)`, or drop the line when it returns None.

    Checkboxes, line endings and every other line are preserved.
    """
    lines = body.splitlines(keepends=True)
    for index in reversed(_item_indices(lines, heading, kind) or []):
        line = lines[index]
        content = line.rstrip("\r\n")
        match = kind.value.fullmatch(content)
        text = match.group(match.lastindex)
        result = fn(text)
        if result is None:
            del lines[index]
        elif result != text:
            prefix = content[: match.start(match.lastindex)]
            lines[index] = prefix + result + line[len(content) :]
    return "".join(lines)
