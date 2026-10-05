import click
import pytest
from click.testing import CliRunner

from chreos import cli_support
from chreos.cli_support import ChreosGroup, confirmer, wants_json
from chreos.errors import ChreosError


@click.group(cls=ChreosGroup)
def root():
    pass


@root.command()
def fails():
    raise ChreosError("nope")


@root.command()
def oserror():
    open("/nonexistent/dir/file")


@root.group()
def sub():
    pass


@sub.command()
def deep():
    raise ChreosError("deep failure")


@pytest.mark.parametrize(("args", "message"), [(["fails"], "nope"), (["sub", "deep"], "deep failure")])
def test_chreos_errors_exit_1(args, message):
    result = CliRunner().invoke(root, args)
    assert result.exit_code == 1
    assert f"Error: {message}" in result.stderr


def test_os_errors_exit_1_without_traceback():
    result = CliRunner().invoke(root, ["oserror"])
    assert result.exit_code == 1
    assert "No such file or directory" in result.stderr
    assert "Traceback" not in result.output


def test_usage_errors_exit_2():
    assert CliRunner().invoke(root, ["bogus"]).exit_code == 2


class TestConfirmer:
    def test_force_always_confirms(self, monkeypatch):
        monkeypatch.setattr(cli_support, "is_interactive", lambda: False)
        assert confirmer(True)("sure?") is True

    def test_no_terminal_fails(self, monkeypatch):
        monkeypatch.setattr(cli_support, "is_interactive", lambda: False)
        with pytest.raises(ChreosError, match="confirmation required.*-f"):
            confirmer(False)("sure?")

    def test_terminal_asks(self, monkeypatch):
        monkeypatch.setattr(cli_support, "is_interactive", lambda: True)
        asked = []
        monkeypatch.setattr(click, "confirm", lambda message, default: asked.append(message) or True)
        assert confirmer(False)("sure?") is True
        assert asked == ["sure?"]


def test_wants_json():
    assert wants_json(True, "text")
    assert wants_json(False, "json")
    assert not wants_json(False, "text")
