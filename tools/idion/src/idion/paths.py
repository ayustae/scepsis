"""Fixed locations (design §2)."""

from pathlib import Path


def context_root() -> Path:
    """`~/.scepsis/context`: the root of the context tree."""
    return Path.home() / ".scepsis" / "context"
