"""Text input for options that take TEXT or standard input (design §6)."""

from pathlib import Path
from typing import TextIO

from idion.errors import IdionError

STDIN = "-"


def read_text_argument(text: str | None, stream: TextIO) -> str:
    """Return `text`, or read `stream` when it's omitted; refuse to wait on a terminal.

    Copied from chreos.
    """
    if text is not None:
        return text
    if stream.isatty():
        raise IdionError(
            "no text given: pass TEXT or pipe it on standard input "
            "(e.g. a heredoc: <<'EOF' ... EOF)"
        )
    content = stream.read()
    return content.removesuffix("\n").removesuffix("\r")


def read_body(body: str | None, body_file: str | None, stream: TextIO) -> str | None:
    """The body given by `-b TEXT`, `-b -` (stdin) or `--body-file PATH`; `None` if none."""
    if body_file is not None:
        try:
            text = Path(body_file).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise IdionError(f"{body_file}: not valid UTF-8") from None
    elif body is not None:
        text = read_text_argument(None if body == STDIN else body, stream)
    else:
        return None
    return check_text(text, "the body")


def read_append_text(text: str, stream: TextIO) -> str:
    """The text given by `-t TEXT` or `-t -` (stdin); it must not be blank."""
    content = read_text_argument(None if text == STDIN else text, stream)
    if not content.strip():
        raise IdionError("the text to append is empty")
    return check_text(content, "the text to append")


def check_text(text: str, what: str) -> str:
    if "\0" in text:
        raise IdionError(f"{what} may not contain NUL characters")
    return text
