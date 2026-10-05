"""One scan of the context tree, used by every listing command (design §2, §7).

The scan never fails on a bad entry: it records a finding and goes on.
Symbolic links are never followed; entries starting with `.` are ignored.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml.comments import CommentedMap

from idion.errors import FormatError
from idion.frontmatter import parse
from idion.identifiers import EXTENSION, MAX_SEGMENTS, Identifier, is_valid_segment
from idion.schema import DESCRIPTION, description_problems

INDEX = "_index.md"
ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    severity: str
    path: Path
    id: str | None
    message: str


@dataclass(frozen=True)
class ContextFile:
    id: Identifier
    path: Path
    description: str | None
    meta: CommentedMap | None


@dataclass(frozen=True)
class Folder:
    id: Identifier
    path: Path
    description: str | None
    index: ContextFile | None


@dataclass
class Tree:
    root: Path
    files: list[ContextFile] = field(default_factory=list)
    folders: list[Folder] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


def scan(root: Path) -> Tree:
    tree = Tree(root)
    _scan_folder(tree, root, ())
    tree.files.sort(key=lambda entry: str(entry.id))
    tree.folders.sort(key=lambda entry: str(entry.id))
    return tree


def _scan_folder(tree: Tree, path: Path, segments: tuple[str, ...]) -> int:
    """Scan one folder; return how many context files it holds, subfolders included."""
    folder_id = Identifier(segments, True)
    try:
        with os.scandir(path) as iterator:
            entries = sorted(iterator, key=lambda entry: entry.name)
    except OSError as error:
        message = f"cannot read folder: {error.strerror}"
        tree.findings.append(Finding(ERROR, path, str(folder_id), message))
        return 0

    index = None
    files = 0
    subfolders = 0
    file_stems = set()
    folder_names = set()
    for entry in entries:
        name = entry.name
        entry_path = path / name
        if name.startswith("."):
            continue
        if entry.is_symlink():
            tree.findings.append(Finding(WARNING, entry_path, None, "symbolic link, ignored"))
        elif entry.is_dir(follow_symlinks=False):
            if not is_valid_segment(name):
                tree.findings.append(Finding(ERROR, entry_path, None, _invalid_name(name)))
            elif len(segments) >= MAX_SEGMENTS:
                message = f"folder nested too deeply (at most {MAX_SEGMENTS} levels), ignored"
                tree.findings.append(Finding(ERROR, entry_path, None, message))
            else:
                subfolders += 1
                folder_names.add(name)
                files += _scan_folder(tree, entry_path, (*segments, name))
        elif entry.is_file(follow_symlinks=False) and name.endswith(EXTENSION):
            if name == INDEX:
                if segments:
                    index = _load(tree, entry_path, folder_id)
                else:
                    tree.findings.append(Finding(ERROR, entry_path, None, "the root may not have an _index.md"))
                continue
            stem = name[: -len(EXTENSION)]
            if not is_valid_segment(stem):
                tree.findings.append(Finding(ERROR, entry_path, None, _invalid_name(name)))
                continue
            files += 1
            file_stems.add(stem)
            tree.files.append(_load(tree, entry_path, Identifier((*segments, stem), False)))
        else:
            tree.findings.append(Finding(WARNING, entry_path, None, "not a context file, ignored"))

    for name in sorted(file_stems & folder_names):
        file_id = str(Identifier((*segments, name), False))
        message = f"a file and a folder share the name {name!r}"
        tree.findings.append(Finding(WARNING, path / f"{name}{EXTENSION}", file_id, message))
    if segments:
        if not files and not subfolders:
            tree.findings.append(Finding(WARNING, path, str(folder_id), "empty folder"))
        elif files and index is None:
            tree.findings.append(Finding(WARNING, path, str(folder_id), "no _index.md: the folder has no description"))
        tree.folders.append(Folder(folder_id, path, index.description if index else None, index))
    return files


def _load(tree: Tree, path: Path, identifier: Identifier) -> ContextFile:
    try:
        meta = parse(path.read_text(encoding="utf-8")).meta
    except (FormatError, UnicodeDecodeError) as error:
        message = "not valid UTF-8" if isinstance(error, UnicodeDecodeError) else str(error)
        tree.findings.append(Finding(ERROR, path, str(identifier), message))
        return ContextFile(identifier, path, None, None)
    problems = description_problems(meta)
    for problem in problems:
        tree.findings.append(Finding(ERROR, path, str(identifier), problem))
    return ContextFile(identifier, path, None if problems else meta[DESCRIPTION], meta)


def _invalid_name(name: str) -> str:
    return (
        f"invalid name {name!r}, ignored: use lowercase letters and digits "
        "separated by single hyphens; names starting with '_' are reserved"
    )
