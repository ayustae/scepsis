import click
import pytest
from click.testing import CliRunner

from idion import cli_support
from idion.cli_support import IdionGroup, confirmer, require_root
from idion.errors import IdionError


@click.group(cls=IdionGroup)
def root():
    pass


@root.command()
def fails():
    raise IdionError("nope")


@root.command()
def oserror():
    open("/nonexistent/dir/file")


@root.group()
def sub():
    pass


@sub.command()
def deep():
    raise IdionError("deep failure")


@pytest.mark.parametrize(("args", "message"), [(["fails"], "nope"), (["sub", "deep"], "deep failure")])
def test_idion_errors_exit_1(args, message):
    result = CliRunner().invoke(root, args)
    assert result.exit_code == 1
    assert f"Error: {message}" in result.stderr


def test_os_errors_exit_1_without_traceback():
    result = CliRunner().invoke(root, ["oserror"])
    assert result.exit_code == 1
    assert "No such file or directory: /nonexistent/dir/file" in result.stderr
    assert "Traceback" not in result.output


def test_usage_errors_exit_2():
    assert CliRunner().invoke(root, ["bogus"]).exit_code == 2


def test_require_root_returns_the_existing_root(home):
    path = home / ".scepsis" / "context"
    path.mkdir(parents=True)
    assert require_root() == path


def test_require_root_tells_to_run_init(home):
    with pytest.raises(IdionError, match=r"no context tree at .*context: run 'idion init' first"):
        require_root()


def test_require_root_rejects_a_file(home):
    (home / ".scepsis").mkdir()
    (home / ".scepsis" / "context").write_text("x")
    with pytest.raises(IdionError, match="is not a folder"):
        require_root()


class TestConfirmer:
    def test_force_says_yes(self, monkeypatch):
        monkeypatch.setattr(cli_support, "is_interactive", lambda: False)
        assert confirmer(True)("Delete?") is True

    @pytest.mark.parametrize("answer", [True, False])
    def test_asks_on_a_terminal(self, monkeypatch, answer):
        monkeypatch.setattr(cli_support, "is_interactive", lambda: True)
        monkeypatch.setattr(click, "confirm", lambda message, default: answer)
        assert confirmer(False)("Delete?") is answer

    def test_fails_without_a_terminal(self, monkeypatch):
        monkeypatch.setattr(cli_support, "is_interactive", lambda: False)
        with pytest.raises(IdionError, match="confirmation required: run in a terminal or pass -f\nDelete\\?"):
            confirmer(False)("Delete?")
