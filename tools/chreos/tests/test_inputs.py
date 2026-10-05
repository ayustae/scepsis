import io

import pytest

from chreos.errors import ChreosError
from chreos.inputs import read_text_argument


class Terminal(io.StringIO):
    def isatty(self):
        return True


def test_argument_wins_over_stdin():
    assert read_text_argument("given", io.StringIO("ignored")) == "given"


def test_empty_argument_is_kept():
    assert read_text_argument("", Terminal()) == ""


def test_reads_stdin_and_drops_one_trailing_newline():
    assert read_text_argument(None, io.StringIO("line one\n\nline two\n")) == "line one\n\nline two"


def test_reads_stdin_without_trailing_newline():
    assert read_text_argument(None, io.StringIO("x")) == "x"


def test_crlf_trailing_newline():
    assert read_text_argument(None, io.StringIO("x\r\n")) == "x"


def test_terminal_without_argument_fails_with_hint():
    with pytest.raises(ChreosError, match="pass TEXT or pipe"):
        read_text_argument(None, Terminal())
