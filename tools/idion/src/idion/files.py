"""Operations on context files and folder descriptions, shared by the commands (design §3, §6)."""

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from idion.errors import FormatError, IdionError
from idion.frontmatter import Document, parse, save
from idion.identifiers import Identifier, resolve
from idion.lock import context_lock
from idion.schema import DESCRIPTION, description_problems
from idion.tree import INDEX


@dataclass(frozen=True)
class LoadedFile:
    """A context file as read from disk; `doc` is `None` when its frontmatter is broken."""

    id: Identifier
    path: Path
    text: str
    doc: Document | None
    problems: list[str]


def default_body(identifier: Identifier) -> str:
    return f"# {identifier.segments[-1]}"


def _body_text(body: str) -> str:
    if not body:
        return ""
    return f"\n{body}" if body.endswith("\n") else f"\n{body}\n"


def create_file(root: Path, identifier: Identifier, description: str, body: str | None) -> Path:
    """Create a context file; `description` is already validated, `body=None` means the default."""
    if body is None:
        body = default_body(identifier)
    with context_lock(root):
        path = resolve(root, identifier)
        if path.exists():
            raise IdionError(f"context file '{identifier}' already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        save(path, Document.new({DESCRIPTION: description}, _body_text(body)))
    return path


def load_file(root: Path, identifier: Identifier) -> LoadedFile:
    """Read a context file; broken frontmatter or descriptions are problems, not errors."""
    path = resolve(root, identifier)
    if not path.is_file():
        raise IdionError(f"no context file '{identifier}' ({path})")
    return load_path(identifier, path)


def load_path(identifier: Identifier, path: Path) -> LoadedFile:
    try:
        text = path.read_text(encoding="utf-8", newline="")
    except UnicodeDecodeError:
        raise IdionError(f"{path}: not valid UTF-8") from None
    try:
        doc = parse(text)
    except FormatError as error:
        return LoadedFile(identifier, path, text, None, [str(error)])
    return LoadedFile(identifier, path, text, doc, description_problems(doc.meta))


def _require_doc(loaded: LoadedFile) -> Document:
    """The CLI never rewrites a file whose frontmatter it can't round-trip."""
    if loaded.doc is None:
        raise IdionError(
            f"{loaded.id}: the frontmatter can't be parsed ({loaded.problems[0]}); "
            "fix it with 'idion edit' or by hand"
        )
    return loaded.doc


def _set_description(loaded: LoadedFile, description: str) -> None:
    doc = _require_doc(loaded)
    if doc.meta.get(DESCRIPTION) != description:
        doc.meta[DESCRIPTION] = description
        save(loaded.path, doc)


def update_description(root: Path, identifier: Identifier, description: str) -> Path:
    """Set the description (already validated); an unchanged value isn't rewritten."""
    with context_lock(root):
        loaded = load_file(root, identifier)
        _set_description(loaded, description)
    return loaded.path


def _with_newline(text: str, newline: str) -> str:
    """`text` with every line break converted to `newline`."""
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)


def appended_body(body: str, text: str, newline: str) -> str:
    """`body` without its trailing line breaks, a blank line, then `text` in the file's newlines."""
    lines = _with_newline(text, newline)
    kept = body.rstrip("\r\n")
    if not kept:
        return f"{newline}{lines}{newline}"
    return f"{kept}{newline}{newline}{lines}{newline}"


def append_text(root: Path, identifier: Identifier, text: str) -> tuple[Path, list[str]]:
    """Append a paragraph to the body; returns the file's problems for warnings."""
    with context_lock(root):
        loaded = load_file(root, identifier)
        doc = _require_doc(loaded)
        doc.body = appended_body(doc.body, text, doc.newline)
        save(loaded.path, doc)
    return loaded.path, loaded.problems


def replaced_body(text: str, newline: str) -> str:
    """`text` laid out as `create` writes a body, in the file's newlines."""
    return _with_newline(_body_text(text), newline)


def replace_body(root: Path, identifier: Identifier, text: str) -> tuple[Path, list[str]]:
    """Replace the body, leaving the frontmatter alone; returns the file's problems for warnings."""
    with context_lock(root):
        loaded = load_file(root, identifier)
        doc = _require_doc(loaded)
        body = replaced_body(text, doc.newline)
        if doc.body != body:
            doc.body = body
            save(loaded.path, doc)
    return loaded.path, loaded.problems


def index_path(root: Path, folder: Identifier) -> Path:
    """`<folder>/_index.md`; the root has none, and the index may not be a symbolic link."""
    if folder.is_root:
        raise IdionError("the root has no description; describe its folders instead")
    path = resolve(root, folder) / INDEX
    if path.is_symlink():
        raise IdionError(f"{folder} is not allowed: {path} is a symbolic link")
    return path


def load_index(root: Path, folder: Identifier) -> LoadedFile:
    path = index_path(root, folder)
    if not path.parent.is_dir():
        raise IdionError(f"no folder '{folder}' ({path.parent})")
    if not path.is_file():
        raise IdionError(f"folder '{folder}' has no description: add one with 'idion folder describe'")
    return load_path(folder, path)


def describe_folder(root: Path, folder: Identifier, description: str) -> Path:
    """Create or update `<folder>/_index.md`, creating the folder if missing."""
    index_path(root, folder)  # refuse invalid input before the lock file is created
    with context_lock(root):
        path = index_path(root, folder)
        if path.is_file():
            _set_description(load_path(folder, path), description)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            save(path, Document.new({DESCRIPTION: description}, ""))
    return path


def _existing(root: Path, identifier: Identifier) -> Path:
    """The path of an existing file or folder (not the root), or an error."""
    path = resolve(root, identifier)
    if identifier.folder and not path.is_dir():
        raise IdionError(f"no folder '{identifier}' ({path})")
    if not identifier.folder and not path.is_file():
        raise IdionError(f"no context file '{identifier}' ({path})")
    return path


def _check_move(root: Path, src: Identifier, dst: Identifier) -> tuple[Path, Path]:
    if src.is_root or dst.is_root:
        raise IdionError("the root can't be moved, and nothing can be moved to it")
    if src.folder != dst.folder:
        kind = "a folder" if dst.folder else "a file"
        raise IdionError(f"'{dst}' is {kind}, but '{src}' is not: move files to files and folders to folders")
    source = _existing(root, src)
    if src.folder and dst.segments[: len(src.segments)] == src.segments:
        raise IdionError(f"'{src}' can't be moved into itself ('{dst}')")
    target = resolve(root, dst)
    if target.exists():
        raise IdionError(f"'{dst}' already exists ({target})")
    return source, target


def move_entry(root: Path, src: Identifier, dst: Identifier) -> Path:
    """Move a file or a folder with everything in it; never overwrites."""
    _check_move(root, src, dst)  # refuse invalid input before the lock file is created
    with context_lock(root):
        source, target = _check_move(root, src, dst)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.rename(source, target)
    return target


def folder_contents(path: Path) -> list[Path]:
    """Everything in a folder except its `_index.md`."""
    return [entry for entry in path.iterdir() if entry.name != INDEX]


def _check_delete(root: Path, identifier: Identifier, force: bool) -> tuple[Path, str]:
    if identifier.is_root:
        raise IdionError("the root can't be deleted")
    path = _existing(root, identifier)
    if not identifier.folder:
        return path, f"Delete context file '{identifier}' ({path})?"
    contents = folder_contents(path)
    if contents and not force:
        noun = "entry" if len(contents) == 1 else "entries"
        raise IdionError(
            f"folder '{identifier}' is not empty ({len(contents)} {noun}); pass -f to delete it with everything in it"
        )
    return path, f"Delete folder '{identifier}' ({path})?"


def delete_entry(root: Path, identifier: Identifier, confirm: Callable[[str], bool], force: bool) -> Path:
    """Delete a file, or a folder with everything in it; confirmed first."""
    path, message = _check_delete(root, identifier, force)
    if not confirm(message):
        raise IdionError("cancelled")
    with context_lock(root):
        path, _ = _check_delete(root, identifier, force)
        if identifier.folder:
            shutil.rmtree(path)
        else:
            path.unlink()
    return path
