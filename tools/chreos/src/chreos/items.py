"""Tolerant loading (design §1): a broken file is reported, never fatal."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from chreos.errors import FormatError
from chreos.frontmatter import Document, load
from chreos.model import Kind
from chreos.schema import Problem, validate


@dataclass
class LoadedItem:
    path: Path
    kind: Kind
    doc: Document
    problems: list[Problem]

    @property
    def valid(self) -> bool:
        return not self.problems

    @property
    def name(self) -> str:
        """The authoritative name: the folder of PROJECT.md/TASK.md, else the file stem (§4)."""
        if self.path.name in ("PROJECT.md", "TASK.md"):
            return self.path.parent.name
        return self.path.stem

    @property
    def project(self) -> str:
        """The owning project, from the path (§4)."""
        if self.path.name == "PROJECT.md":
            return self.path.parent.name
        if self.path.name == "TASK.md":  # <project>/tasks/<name>/TASK.md
            return self.path.parents[2].name
        return self.path.parents[1].name  # <project>/.archive/ or <project>/decisions/


@dataclass(frozen=True)
class LoadFailure:
    path: Path
    message: str


def load_item(path: Path, kind: Kind) -> LoadedItem:
    """Load and validate one item; raise `FormatError` or `OSError` if it can't be read."""
    doc = load(path)
    return LoadedItem(path, kind, doc, validate(kind, doc.meta))


def load_items(
    paths: Iterable[Path], kind: Kind
) -> tuple[list[LoadedItem], list[LoadFailure]]:
    """Load every readable item; unreadable ones become failures instead of errors."""
    items, failures = [], []
    for path in paths:
        try:
            items.append(load_item(path, kind))
        except FormatError as error:
            failures.append(LoadFailure(path, str(error)))
        except OSError as error:
            failures.append(LoadFailure(path, f"{path}: {error.strerror or error}"))
    return items, failures
