"""Body sections (design §9): locate, read and write one `## <heading>` section.

A section is an exact `## <heading>` line outside fenced code and runs until
the next unfenced `## ` line or the end of the body. Writes touch only that
section; every other byte is preserved. A missing section is recreated in
template position: after the nearest preceding template section that exists,
else before the nearest following one, else at the end of the body.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from chreos.errors import ChreosError
from chreos.markdown import has_unclosed_fence, newline_of, unfenced

TASK_SECTIONS = ("Description", "Acceptance criteria", "References", "Notes")
PROJECT_SECTIONS = ("Description",)
DECISION_SECTIONS = ("Description",)
H1_OR_H2 = re.compile(r"#{1,2}(\s|$)")


@dataclass(frozen=True)
class Span:
    heading: int  # index of the `## ` line
    start: int  # first content line
    end: int  # next `## ` line, or len(lines)


def _is_blank(line: str) -> bool:
    return not line.strip()


def _h2_indices(lines: Sequence[str]) -> list[int]:
    return [
        index
        for index, line in unfenced(lines)
        if line.startswith("## ") or line.rstrip("\r\n") == "##"
    ]


def find_section(lines: Sequence[str], heading: str) -> Span | None:
    h2s = _h2_indices(lines)
    for position, index in enumerate(h2s):
        if lines[index].rstrip("\r\n") == f"## {heading}":
            end = h2s[position + 1] if position + 1 < len(h2s) else len(lines)
            return Span(index, index + 1, end)
    return None


def _trim_blank(lines: list[str]) -> list[str]:
    start, end = 0, len(lines)
    while start < end and _is_blank(lines[start]):
        start += 1
    while end > start and _is_blank(lines[end - 1]):
        end -= 1
    return lines[start:end]


def read_section(body: str, heading: str) -> str | None:
    """The section's content without surrounding blank lines; None if missing."""
    lines = body.splitlines(keepends=True)
    span = find_section(lines, heading)
    if span is None:
        return None
    content = "".join(_trim_blank(lines[span.start : span.end]))
    return content.removesuffix("\n").removesuffix("\r")


def _content(text: str, newline: str, at_end: bool) -> list[str]:
    """Blank line, the text, and a blank line unless the section ends the body."""
    text_lines = [line + newline for line in _trim_blank(text.splitlines())]
    if not text_lines:
        return [newline]
    return [newline, *text_lines, *([] if at_end else [newline])]


def _terminate(lines: list[str], index: int, newline: str) -> None:
    if not lines[index].endswith(("\n", "\r")):
        lines[index] += newline


def _insertion_point(lines: list[str], heading: str, order: Sequence[str]) -> int:
    position = order.index(heading)
    for previous in reversed(order[:position]):
        if span := find_section(lines, previous):
            return span.end
    for following in order[position + 1 :]:
        if span := find_section(lines, following):
            return span.heading
    return len(lines)


def write_section(body: str, heading: str, text: str, order: Sequence[str]) -> str:
    """Replace the section's content with `text`, recreating the section if missing."""
    if heading not in order:
        raise ValueError(f"unknown section {heading!r}")
    newline = newline_of(body)
    lines = body.splitlines(keepends=True)
    span = find_section(lines, heading)
    if span is not None:
        _terminate(lines, span.heading, newline)
        lines[span.start : span.end] = _content(text, newline, span.end == len(lines))
        return "".join(lines)

    index = _insertion_point(lines, heading, order)
    block = [f"## {heading}{newline}", *_content(text, newline, index == len(lines))]
    if index > 0:
        _terminate(lines, index - 1, newline)
        if not _is_blank(lines[index - 1]):
            block.insert(0, newline)
    lines[index:index] = block
    return "".join(lines)


def append_text(body: str, heading: str, text: str, order: Sequence[str]) -> str:
    """Add `text` after the section's content, separated by a blank line."""
    existing = read_section(body, heading)
    combined = f"{existing}\n\n{text}" if existing else text
    return write_section(body, heading, combined, order)


def validate_description(text: str) -> str:
    """Refuse content that would break section boundaries."""
    lines = text.splitlines(keepends=True)
    for _, line in unfenced(lines):
        if H1_OR_H2.match(line.rstrip("\r\n")):
            raise ChreosError(
                f"the description must not contain H1 or H2 heading lines: {line.strip()!r}; "
                "use ### or deeper"
            )
    if has_unclosed_fence(lines):
        raise ChreosError("the description has an unclosed code fence")
    return text
