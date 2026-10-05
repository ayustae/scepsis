import io

import pytest

from idion.errors import IdionError
from idion.inputs import read_append_text, read_body, read_text_argument


class Terminal(io.StringIO):
    def isatty(self):
        return True


def test_text_is_returned_as_is():
    assert read_text_argument("a\n", io.StringIO("ignored")) == "a\n"


def test_stdin_is_read_without_one_trailing_newline():
    assert read_text_argument(None, io.StringIO("a\nb\n\n")) == "a\nb\n"
    assert read_text_argument(None, io.StringIO("a\r\n")) == "a"


def test_a_terminal_is_never_waited_on():
    with pytest.raises(IdionError, match="pipe it on standard input"):
        read_text_argument(None, Terminal())


def test_no_body():
    assert read_body(None, None, io.StringIO("x")) is None


def test_body_text():
    assert read_body("# Hi", None, io.StringIO("x")) == "# Hi"


def test_body_dash_reads_stdin():
    assert read_body("-", None, io.StringIO("# From stdin\n")) == "# From stdin"


def test_body_file(tmp_path):
    path = tmp_path / "body.md"
    path.write_text("# Ünïcode\n\ntext\n", encoding="utf-8")
    assert read_body(None, str(path), io.StringIO()) == "# Ünïcode\n\ntext\n"


def test_body_file_must_be_utf8(tmp_path):
    path = tmp_path / "body.md"
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(IdionError, match="not valid UTF-8"):
        read_body(None, str(path), io.StringIO())


@pytest.mark.parametrize("source", ["text", "stdin", "file"])
def test_nul_is_rejected(tmp_path, source):
    path = tmp_path / "body.md"
    path.write_text("a\0b")
    args = {
        "text": ("a\0b", None, io.StringIO()),
        "stdin": ("-", None, io.StringIO("a\0b")),
        "file": (None, str(path), io.StringIO()),
    }[source]
    with pytest.raises(IdionError, match="NUL"):
        read_body(*args)


def test_append_text_is_returned():
    assert read_append_text("More.", io.StringIO()) == "More."


def test_append_text_from_stdin():
    assert read_append_text("-", io.StringIO("A\nB\n")) == "A\nB"


@pytest.mark.parametrize(("text", "stdin", "message"), [("", "", "empty"), ("  \n ", "", "empty"), ("-", "\n\n", "empty"), ("a\0", "", "NUL")])
def test_invalid_append_text(text, stdin, message):
    with pytest.raises(IdionError, match=message):
        read_append_text(text, io.StringIO(stdin))
