"""Identifiers of context files and folders, and their safe paths (design §4).

A file is its path relative to the root without `.md` (`teams/my-team`), a
folder the same with a trailing `/` (`teams/`), the root is `/`. Input is
validated, never rewritten.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

from idion.errors import IdionError

SEGMENT_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
SEGMENT_MAX_LENGTH = 64
MAX_SEGMENTS = 8
EXTENSION = ".md"
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class Identifier:
    segments: tuple[str, ...]
    folder: bool

    @property
    def is_root(self) -> bool:
        return not self.segments

    def __str__(self) -> str:
        if self.is_root:
            return "/"
        text = "/".join(self.segments)
        return f"{text}/" if self.folder else text


ROOT = Identifier((), True)


def is_valid_segment(name: object) -> bool:
    return (
        isinstance(name, str)
        and len(name) <= SEGMENT_MAX_LENGTH
        and SEGMENT_PATTERN.fullmatch(name) is not None
    )


def _check_segment(text: str, segment: str) -> None:
    if segment in (".", ".."):
        raise IdionError(f"invalid identifier {text!r}: '.' and '..' are not allowed")
    if segment.startswith("_"):
        raise IdionError(f"invalid identifier {text!r}: names starting with '_' are reserved")
    if segment.endswith(EXTENSION):
        raise IdionError(f"invalid identifier {text!r}: drop the .md extension")
    if not is_valid_segment(segment):
        raise IdionError(
            f"invalid identifier {text!r}: invalid segment {segment!r}; use lowercase letters "
            f"and digits separated by single hyphens, at most {SEGMENT_MAX_LENGTH} characters"
        )


def parse_identifier(text: object) -> Identifier:
    """Parse a file or folder identifier; reject anything that isn't canonical."""
    if not isinstance(text, str):
        raise IdionError(f"invalid identifier {text!r}: not text")
    if not text:
        raise IdionError("invalid identifier: empty")
    if CONTROL.search(text):
        raise IdionError(f"invalid identifier {text!r}: control characters are not allowed")
    if text == "/":
        return ROOT
    if text.startswith("/"):
        raise IdionError(
            f"invalid identifier {text!r}: absolute paths are not allowed; "
            "use a path relative to the context root"
        )
    folder = text.endswith("/")
    segments = tuple((text[:-1] if folder else text).split("/"))
    if "" in segments:
        raise IdionError(f"invalid identifier {text!r}: empty segment")
    if len(segments) > MAX_SEGMENTS:
        raise IdionError(f"invalid identifier {text!r}: at most {MAX_SEGMENTS} segments")
    for segment in segments:
        _check_segment(text, segment)
    return Identifier(segments, folder)


def parse_file_id(text: object) -> Identifier:
    identifier = parse_identifier(text)
    if identifier.folder:
        hint = "" if identifier.is_root else f"; did you mean {str(identifier)[:-1]!r}?"
        raise IdionError(f"{str(identifier)!r} is a folder, not a file{hint}")
    return identifier


def parse_folder_id(text: object) -> Identifier:
    identifier = parse_identifier(text)
    if not identifier.folder:
        raise IdionError(f"{text!r} is a file, not a folder; did you mean '{identifier}/'?")
    return identifier


def resolve(root: Path, identifier: Identifier) -> Path:
    """The path of `identifier` under `root`, refusing symbolic links below the root.

    The root itself may be a symbolic link; the path need not exist yet.
    """
    names = list(identifier.segments)
    if names and not identifier.folder:
        names[-1] += EXTENSION
    path = root
    for name in names:
        path = path / name
        if path.is_symlink():
            raise IdionError(f"{identifier} is not allowed: {path} is a symbolic link")
    real_root = os.path.realpath(root)
    if os.path.commonpath([real_root, os.path.realpath(path)]) != real_root:
        raise IdionError(f"{identifier} is not allowed: {path} is outside {root}")
    return path
