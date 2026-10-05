"""The path rule (design §13): absolute or `~` everywhere, relative only for task sources."""

from pathlib import Path

from chreos.errors import ChreosError


def _check_text(value: str) -> None:
    if not value or "\0" in value or "\n" in value or "\r" in value:
        raise ChreosError(f"invalid path {value!r}")


def parse_path(value: str) -> Path:
    """Return an absolute path; `~` is expanded, relative paths are refused."""
    _check_text(value)
    if not (value.startswith("/") or value == "~" or value.startswith("~/")):
        raise ChreosError(f"invalid path {value!r}: it must be absolute or start with '~'")
    return Path(value).expanduser()


def parse_source_path(value: str) -> str:
    """Validate a task `source.path`; it is stored exactly as given (§3.3)."""
    _check_text(value)
    return value


def scepsis_home() -> Path:
    """`~/.scepsis`: framework config and template overrides (§13)."""
    return Path.home() / ".scepsis"
