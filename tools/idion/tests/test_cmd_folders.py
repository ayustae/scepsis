import json

import pytest

from idion.cli import main


@pytest.fixture
def root(home):
    path = home / ".scepsis" / "context"
    path.mkdir(parents=True)
    return path


def test_describe_prints_the_path_and_feeds_list(runner, root):
    runner.invoke(main, ["create", "teams/my-team", "-d", "My team."])
    result = runner.invoke(main, ["folder", "describe", "teams/", "-d", "  Teams.  "])
    assert result.exit_code == 0, result.output
    assert result.stdout == f"{root / 'teams' / '_index.md'}\n"
    listing = runner.invoke(main, ["list", "--depth", "1"])
    assert listing.stdout == "teams/ — Teams. (1 file)\n"
    assert listing.stderr == ""


def test_describe_creates_a_nested_folder(runner, root):
    assert runner.invoke(main, ["folder", "describe", "company/projects/", "-d", "Projects."]).exit_code == 0
    assert (root / "company" / "projects" / "_index.md").is_file()


@pytest.mark.parametrize(
    ("folder", "description", "message"),
    [
        ("teams", "x", "did you mean 'teams/'"),
        ("/", "x", "the root has no description"),
        ("teams/", "two\nlines", "single line"),
        ("Teams/", "x", "invalid segment"),
    ],
)
def test_describe_errors_write_nothing(runner, root, folder, description, message):
    result = runner.invoke(main, ["folder", "describe", folder, "-d", description])
    assert result.exit_code == 1
    assert message in result.stderr
    assert list(root.iterdir()) == []


def test_show_text_is_the_raw_index(runner, root):
    (root / "teams").mkdir()
    (root / "teams" / "_index.md").write_text("---\ndescription: Teams.  # c\n---\n\nNotes.\n")
    result = runner.invoke(main, ["folder", "show", "teams/"])
    assert result.exit_code == 0
    assert result.stdout == "---\ndescription: Teams.  # c\n---\n\nNotes.\n"


def test_show_json(runner, root):
    runner.invoke(main, ["folder", "describe", "teams/", "-d", "Teams."])
    result = runner.invoke(main, ["folder", "show", "teams/", "--json"])
    assert json.loads(result.stdout) == {
        "id": "teams/",
        "path": str(root / "teams" / "_index.md"),
        "frontmatter": {"description": "Teams."},
        "body": "",
        "problems": [],
    }


def test_show_broken_index_warns(runner, root):
    (root / "teams").mkdir()
    (root / "teams" / "_index.md").write_text("junk\n")
    result = runner.invoke(main, ["folder", "show", "teams/"])
    assert result.exit_code == 0
    assert result.stdout == "junk\n"
    assert result.stderr.startswith("warning: ")


@pytest.mark.parametrize(
    ("setup", "message"),
    [(False, "no folder 'teams/'"), (True, "has no description")],
)
def test_show_errors(runner, root, setup, message):
    if setup:
        (root / "teams").mkdir()
    result = runner.invoke(main, ["folder", "show", "teams/"])
    assert result.exit_code == 1
    assert message in result.stderr


def test_missing_root(runner, home):
    result = runner.invoke(main, ["folder", "show", "teams/"])
    assert result.exit_code == 1
    assert "idion init" in result.stderr


def test_folder_help_lists_subcommands(runner):
    result = runner.invoke(main, ["folder", "-h"])
    assert result.exit_code == 0
    assert "describe" in result.stdout and "show" in result.stdout
