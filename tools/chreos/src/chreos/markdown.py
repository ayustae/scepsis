"""Minimal Markdown line handling shared by the body and section code."""

import re
from collections.abc import Iterator, Sequence

FENCE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)")


def _fence_scan(lines: Sequence[str]) -> Iterator[tuple[int, str, bool]]:
    """Yield (index, line, inside_fence) where fence marker lines count as inside."""
    opening: str | None = None
    for index, line in enumerate(lines):
        match = FENCE.match(line.rstrip("\r\n"))
        if opening is None:
            if match and not ("`" in match.group(2) and match.group(1)[0] == "`"):
                opening = match.group(1)
                yield index, line, True
                continue
            yield index, line, False
        else:
            if (
                match
                and match.group(1)[0] == opening[0]
                and len(match.group(1)) >= len(opening)
                and not match.group(2).strip()
            ):
                opening = None
            yield index, line, True


def unfenced(lines: Sequence[str]) -> Iterator[tuple[int, str]]:
    """Yield (index, line) for lines outside fenced code blocks."""
    for index, line, inside in _fence_scan(lines):
        if not inside:
            yield index, line


def has_unclosed_fence(lines: Sequence[str]) -> bool:
    """True when a fence opened in `lines` is never closed."""
    *_, (_, _, inside) = _fence_scan([*lines, ""])
    return inside


def newline_of(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"
