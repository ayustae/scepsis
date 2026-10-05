"""`list`: context files with deeper levels collapsed into folders (design §5).

A pure function over a scanned tree. Depth counts segments below the prefix;
a file deeper than the depth is replaced by its folder at that depth.
"""

from dataclasses import dataclass
from pathlib import Path

from idion.identifiers import Identifier
from idion.tree import ContextFile, Finding, Folder, Tree

FILE = "file"
FOLDER = "folder"


@dataclass(frozen=True)
class Entry:
    id: Identifier
    kind: str
    description: str | None
    path: Path
    files: int | None = None  # set on collapsed folders only


def _matches(file: ContextFile, search: str) -> bool:
    needle = search.casefold()
    return needle in str(file.id).casefold() or needle in (file.description or "").casefold()


def build_listing(
    tree: Tree,
    prefix: Identifier,
    depth: int | None = None,
    folders: bool = False,
    search: str | None = None,
) -> list[Entry]:
    base = len(prefix.segments)

    def below_prefix(segments: tuple[str, ...]) -> bool:
        return len(segments) > base and segments[:base] == prefix.segments

    files = [
        file for file in tree.files
        if below_prefix(file.id.segments) and (search is None or _matches(file, search))
    ]
    folder_by_segments: dict[tuple[str, ...], Folder] = {folder.id.segments: folder for folder in tree.folders}

    entries: list[Entry] = []
    collapsed: dict[tuple[str, ...], int] = {}
    holding: set[tuple[str, ...]] = set()  # folders that hold at least one listed file
    for file in files:
        segments = file.id.segments
        for end in range(base + 1, len(segments)):
            holding.add(segments[:end])
        if depth is not None and len(segments) - base > depth:
            key = segments[: base + depth]
            collapsed[key] = collapsed.get(key, 0) + 1
        else:
            entries.append(Entry(file.id, FILE, file.description, file.path))

    for segments, count in collapsed.items():
        folder = folder_by_segments.get(segments)
        description = folder.description if folder else None
        entries.append(Entry(Identifier(segments, True), FOLDER, description, tree.root.joinpath(*segments), count))

    if folders:
        for segments in holding:
            folder = folder_by_segments.get(segments)
            relative = len(segments) - base
            if folder and folder.description and (depth is None or relative < depth):
                entries.append(Entry(folder.id, FOLDER, folder.description, folder.path))

    return sorted(entries, key=lambda entry: str(entry.id))


def findings_under(tree: Tree, path: Path) -> list[Finding]:
    return [finding for finding in tree.findings if finding.path.is_relative_to(path)]
