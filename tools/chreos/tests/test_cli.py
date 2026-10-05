import pytest
from click.testing import CliRunner

from chreos import __version__
from chreos.cli import main


class ChreosRunner(CliRunner):
    def invoke(self, cli, args=None, **kwargs):
        kwargs.setdefault("prog_name", "chreos")
        return super().invoke(cli, args, **kwargs)


@pytest.fixture
def runner():
    return ChreosRunner()


def test_version_is_read_from_package_metadata():
    assert __version__ == "0.2.0"


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_version_flag_prints_name_and_version(runner, flag):
    result = runner.invoke(main, [flag])
    assert result.exit_code == 0
    assert result.output == f"chreos {__version__}\n"


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_flag_prints_usage(runner, flag):
    result = runner.invoke(main, [flag])
    assert result.exit_code == 0
    assert result.output.startswith("Usage: chreos")


def test_no_arguments_prints_usage_as_a_usage_error(runner):
    result = runner.invoke(main, [])
    assert result.exit_code == 2
    assert result.output.startswith("Usage: chreos")


def test_unknown_command_is_a_usage_error(runner):
    result = runner.invoke(main, ["nonexistent"])
    assert result.exit_code == 2
