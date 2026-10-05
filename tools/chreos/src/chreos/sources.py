"""Task sources (design §11.2): where the work of an open task happens."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from chreos import git
from chreos.errors import ChreosError
from chreos.model import Phase, SourceType
from chreos.paths import parse_path

Bases = Mapping[SourceType, Path | None]


@dataclass(frozen=True)
class Source:
    type: SourceType
    path: str  # stored exactly as given; may be relative to the base folder of its type

    @classmethod
    def from_meta(cls, value: object) -> "Source | None":
        if value is None:
            return None
        try:
            if not isinstance(value, Mapping) or not value.get("path"):
                raise ValueError
            return cls(SourceType(value.get("type")), str(value["path"]))
        except ValueError:
            raise ChreosError(
                f"invalid source {value!r}: needs 'type' (git or local) and 'path'"
            ) from None


def resolve(source: Source, bases: Bases) -> Path:
    if source.path.startswith(("/", "~")):
        return parse_path(source.path)
    base = bases.get(source.type)
    if base is None:
        raise ChreosError(
            f"relative {source.type} source '{source.path}' needs a base folder: "
            f"set source.{source.type}_path in the config"
        )
    return Path(base) / source.path


def _check(source: Source, bases: Bases) -> tuple[Path, Path | None]:
    resolved = resolve(source, bases)
    if not resolved.is_dir():
        raise ChreosError(f"source path {resolved} does not exist or is not a directory")
    if source.type is SourceType.LOCAL:
        return resolved, None
    git.check_version()  # a missing or too old git is reported as such
    try:
        return resolved, git.toplevel(resolved)
    except git.GitError:
        raise ChreosError(f"source path {resolved} is not inside a git repository") from None


def source_warnings(source: Source, bases: Bases) -> list[str]:
    """Problems reported as warnings by create/update (§11.2)."""
    try:
        _check(source, bases)
    except ChreosError as error:
        return [str(error)]
    return []


def require_source(meta: Mapping, bases: Bases) -> tuple[Source, Path, Path | None]:
    """The source of a task being opened: (source, resolved path, git repository root)."""
    source = Source.from_meta(meta.get("source"))
    if source is None:
        raise ChreosError(
            "the task has no source; set one with --source-type and --source-path first"
        )
    return (source, *_check(source, bases))


def check_source_change(phase: str) -> None:
    if phase == Phase.OPEN:
        raise ChreosError("the source of an open task cannot be changed; close it first")
