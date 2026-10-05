import json

import pytest
import tomlkit
from click.testing import CliRunner

from chreos import cli_support
from chreos.cli import main
from chreos.config import config_path, load_config


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(cli_support, "is_interactive", lambda: False)
    return tmp_path


def run(*args, input=None):
    return CliRunner().invoke(main, list(args), prog_name="chreos", input=input)


@pytest.fixture
def initialized(home):
    result = run("init", "--workspace-path", "~/ws")
    assert result.exit_code == 0, result.output
    return home


class TestInit:
    def test_fresh(self, home):
        (home / "code").mkdir()
        result = run("init", "--workspace-path", "~/ws", "--source-git-path", "~/code")
        assert result.exit_code == 0, result.output
        assert (home / "ws" / "default" / "PROJECT.md").is_file()
        for folder in ("tasks", ".archive", "decisions"):
            assert (home / "ws" / "default" / folder).is_dir()
        config = load_config()
        assert config.workspace == home / "ws"
        assert config.default_project == "default"
        doc = tomlkit.parse(config_path().read_text())
        assert doc["workspace"]["path"] == "~/ws"  # stored as given
        assert "warning" not in result.stderr

    def test_custom_default_project_and_missing_base_warning(self, home):
        result = run("init", "--workspace-path", "~/ws", "--default-project", "inbox", "--source-local-path", "~/files")
        assert result.exit_code == 0, result.output
        assert (home / "ws" / "inbox" / "PROJECT.md").is_file()
        assert "warning: " in result.stderr and "files" in result.stderr

    def test_prompts_for_workspace_on_a_terminal(self, home, monkeypatch):
        monkeypatch.setattr(cli_support, "is_interactive", lambda: True)
        result = run("init", input="~/prompted\n")
        assert result.exit_code == 0, result.output
        assert (home / "prompted" / "default" / "PROJECT.md").is_file()

    def test_workspace_required_without_a_terminal(self, home):
        result = run("init")
        assert result.exit_code == 2
        assert "--workspace-path" in result.stderr

    @pytest.mark.parametrize(
        "args",
        [
            ["--workspace-path", "relative"],
            ["--workspace-path", "~/ws", "--default-project", "Bad"],
            ["--workspace-path", "~/ws", "--source-git-path", "code"],
        ],
    )
    def test_invalid_input_writes_nothing(self, home, args):
        result = run("init", *args)
        assert result.exit_code == 1
        assert not config_path().exists()
        assert not (home / "ws").exists()

    def test_existing_config_needs_confirmation(self, initialized):
        before = config_path().read_text()
        result = run("init", "--workspace-path", "~/other")
        assert result.exit_code == 1
        assert "confirmation required" in result.stderr
        assert config_path().read_text() == before

    def test_existing_config_confirmed_on_terminal(self, initialized, monkeypatch):
        monkeypatch.setattr(cli_support, "is_interactive", lambda: True)
        result = run("init", "--workspace-path", "~/other", input="y\n")
        assert result.exit_code == 0, result.output
        assert load_config().workspace == initialized / "other"

    def test_force_overwrites_and_keeps_existing_projects(self, initialized):
        project = initialized / "ws" / "default" / "PROJECT.md"
        project.write_text(project.read_text().replace("status: active", "status: inactive"))
        result = run("init", "--workspace-path", "~/ws", "-f")
        assert result.exit_code == 0, result.output
        assert "status: inactive" in project.read_text()


class TestConfig:
    def test_show_text(self, initialized):
        result = run("config", "show")
        assert result.exit_code == 0
        assert result.output == "workspace.path = ~/ws\ndefaults.project = default\n"

    def test_show_json(self, initialized):
        result = run("config", "show", "--json")
        assert json.loads(result.output) == {"workspace": {"path": "~/ws"}, "defaults": {"project": "default"}}

    def test_get(self, initialized):
        assert run("config", "get", "defaults.project").output == "default\n"
        assert run("config", "get", "source.git_path").output == ""
        assert json.loads(run("config", "get", "source.git_path", "--json").output) is None

    def test_set_and_output_format(self, initialized):
        assert run("config", "set", "output.format", "json").exit_code == 0
        assert json.loads(run("config", "get", "output.format").output) == "json"
        assert "workspace" in json.loads(run("config", "show").output)

    def test_set_errors(self, initialized):
        result = run("config", "set", "defaults.project", "missing")
        assert result.exit_code == 1
        assert "no project 'missing'" in result.stderr
        assert run("config", "set", "nope.key", "x").exit_code == 1
        assert run("config", "set", "defaults.project").exit_code == 2

    def test_without_config(self, home):
        result = run("config", "show")
        assert result.exit_code == 1
        assert "chreos init" in result.stderr

    def test_help_short_flag_on_subcommands(self, home):
        assert run("config", "set", "-h").exit_code == 0
        assert run("init", "-h").exit_code == 0


def all_commands(command, path=("chreos",)):
    yield path, command
    for name, sub in getattr(command, "commands", {}).items():
        yield from all_commands(sub, (*path, name))


def test_every_command_has_help_text():
    for path, command in all_commands(main):
        assert command.help and command.help.strip(), " ".join(path)
