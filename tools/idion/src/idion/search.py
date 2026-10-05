"""`search`: context files whose identifier, description or body contains a text."""

from dataclasses import dataclass, field
from pathlib import Path

from idion.errors import FormatError
from idion.frontmatter import parse
from idion.identifiers import Identifier
from idion.tree import Tree


@dataclass(frozen=True)
class Line:
    number: int  # 1-based, in the file
    text: str


@dataclass(frozen=True)
class Match:
    id: Identifier
    path: Path
    description: str | None
    lines: list[Line] = field(default_factory=list)


def body_lines(text: str) -> list[Line]:
    """The body's lines numbered as in the file; the whole text when the frontmatter is broken."""
    lines = text.splitlines()
    try:
        body = parse(text).body.splitlines()
    except FormatError:
        body = lines
    offset = len(lines) - len(body)
    return [Line(offset + index + 1, line) for index, line in enumerate(body)]


def search_tree(tree: Tree, prefix: Identifier, text: str) -> list[Match]:
    """Case-insensitive substring search, files in identifier order; unreadable files are skipped."""
    needle = text.casefold()
    base = len(prefix.segments)
    matches = []
    for file in tree.files:
        if len(file.id.segments) <= base or file.id.segments[:base] != prefix.segments:
            continue
        try:
            content = file.path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lines = [line for line in body_lines(content) if needle in line.text.casefold()]
        header = needle in str(file.id).casefold() or needle in (file.description or "").casefold()
        if lines or header:
            matches.append(Match(file.id, file.path, file.description, lines))
    return matches
