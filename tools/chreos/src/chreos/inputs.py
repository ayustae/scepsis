"""Text input for commands that take TEXT or standard input (design §9)."""

from typing import TextIO

from chreos.errors import ChreosError


def read_text_argument(text: str | None, stream: TextIO) -> str:
    """Return `text`, or read `stream` when it's omitted; refuse to wait on a terminal."""
    if text is not None:
        return text
    if stream.isatty():
        raise ChreosError(
            "no text given: pass TEXT or pipe it on standard input "
            "(e.g. a heredoc: <<'EOF' ... EOF)"
        )
    content = stream.read()
    return content.removesuffix("\n").removesuffix("\r")
