"""Keeping the body's H1 and summary paragraph in sync with `title`/`summary` (design §8).

The H1 is the first `# ` line outside fenced code; the summary paragraph is
the paragraph right after it, unless that is a heading. Each is changed only
if it still matches the old value exactly; otherwise it's left untouched and
a warning is returned. Every other byte of the body is preserved.
"""

from chreos.markdown import newline_of, unfenced


def _is_blank(line: str) -> bool:
    return not line.strip()


def find_h1(lines: list[str]) -> int | None:
    return next((index for index, line in unfenced(lines) if line.startswith("# ")), None)


def _summary_span(lines: list[str], h1: int) -> tuple[int, int]:
    """(start, end) of the paragraph after the H1; start == end when there is none."""
    start = h1 + 1
    while start < len(lines) and _is_blank(lines[start]):
        start += 1
    if start == len(lines) or lines[start].startswith("#"):
        return start, start
    end = start
    while end < len(lines) and not _is_blank(lines[end]):
        end += 1
    return start, end


def _text(lines: list[str]) -> str:
    return "\n".join(line.rstrip("\r\n") for line in lines)


def sync_heading(
    body: str,
    old_title: str,
    new_title: str,
    old_summary: str | None,
    new_summary: str | None,
) -> tuple[str, list[str]]:
    title_changed = new_title != old_title
    summary_changed = new_summary != old_summary
    if not (title_changed or summary_changed):
        return body, []

    lines = body.splitlines(keepends=True)
    h1 = find_h1(lines)
    if h1 is None:
        warnings = []
        if title_changed:
            warnings.append("the body has no H1; it was left unchanged")
        if summary_changed:
            warnings.append("the body has no H1, so its summary paragraph was left unchanged")
        return body, warnings

    newline = lines[h1][len(lines[h1].rstrip("\r\n")) :] or newline_of(body)
    lines[h1] = lines[h1].rstrip("\r\n") + newline
    warnings = []

    if title_changed:
        if lines[h1].rstrip("\r\n") == f"# {old_title}":
            lines[h1] = f"# {new_title}{newline}"
        else:
            warnings.append("the body's H1 differs from the old title; it was left unchanged")

    if summary_changed:
        start, end = _summary_span(lines, h1)
        new_lines = []
        if new_summary is not None:
            new_lines.append(new_summary.replace("\n", newline) + newline)
        if old_summary is None and start == end:
            after = h1 + 1
            if after < len(lines) and not _is_blank(lines[after]):
                new_lines.append(newline)
            lines[after:after] = [newline, *new_lines]
        elif old_summary is not None and start < end and _text(lines[start:end]) == old_summary:
            lines[start:end] = new_lines
            if new_summary is None:
                if start < len(lines) and _is_blank(lines[start]):
                    del lines[start]
                elif start == len(lines) and _is_blank(lines[start - 1]):
                    del lines[start - 1]
        else:
            warnings.append(
                "the body's summary paragraph differs from the old summary; it was left unchanged"
            )

    return "".join(lines), warnings
