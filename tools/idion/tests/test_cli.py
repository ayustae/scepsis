import pytest

from idion import __version__
from idion.cli import main


def test_version_is_read_from_package_metadata():
    assert __version__ == "0.2.0"


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_version_flag_prints_name_and_version(runner, flag):
    result = runner.invoke(main, [flag])
    assert result.exit_code == 0
    assert result.output == f"idion {__version__}\n"


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_flag_prints_usage(runner, flag):
    result = runner.invoke(main, [flag])
    assert result.exit_code == 0
    assert result.output.startswith("Usage: idion")


def test_no_arguments_prints_usage_as_a_usage_error(runner):
    result = runner.invoke(main, [])
    assert result.exit_code == 2
    assert result.output.startswith("Usage: idion")
