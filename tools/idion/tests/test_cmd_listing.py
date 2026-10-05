import json

import pytest

from idion.cli import main


@pytest.fixture
def root(home):
    path = home / ".scepsis" / "context"
    for rel, description in {
        "user.md": "The user.",
        "teams/_index.md": "Teams.",
        "teams/my-team.md": "My team.",
        "teams/data-platform.md": "Data Platform.",
    }.items():
        file = path / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(f"---\ndescription: {description}\n---\n")
    return path


def test_text(runner, root):
    result = runner.invoke(main, ["list"])
    assert result.exit_code == 0
    assert result.stdout == "teams/data-platform — Data Platform.\nteams/my-team — My team.\nuser — The user.\n"
    assert result.stderr == ""


def test_depth(runner, root):
    result = runner.invoke(main, ["list", "--depth", "1"])
    assert result.stdout == "teams/ — Teams. (2 files)\nuser — The user.\n"


def test_options(runner, root):
    result = runner.invoke(main, ["list", "/", "--folders", "-S", "MY"])
    assert result.stdout == "teams/ — Teams.\nteams/my-team — My team.\n"


def test_the_prefix_folder_itself_is_not_listed(runner, root):
    result = runner.invoke(main, ["list", "teams/", "--folders"])
    assert result.stdout == "teams/data-platform — Data Platform.\nteams/my-team — My team.\n"


def test_json(runner, root):
    result = runner.invoke(main, ["list", "--depth", "1", "--json"])
    assert json.loads(result.stdout) == [
        {"id": "teams/", "kind": "folder", "description": "Teams.", "path": str(root / "teams"), "files": 2},
        {"id": "user", "kind": "file", "description": "The user.", "path": str(root / "user.md")},
    ]


def test_empty_listing(runner, root):
    result = runner.invoke(main, ["list", "-S", "nothing"])
    assert (result.exit_code, result.stdout) == (0, "")
    assert json.loads(runner.invoke(main, ["list", "-S", "nothing", "--json"]).stdout) == []


def test_problems_are_summarized_on_stderr(runner, root):
    (root / "notes.txt").write_text("x")
    (root / "broken.md").write_text("x")
    result = runner.invoke(main, ["list", "--depth", "1"])
    assert result.exit_code == 0
    assert result.stdout == "broken — (invalid description)\nteams/ — Teams. (2 files)\nuser — The user.\n"
    assert result.stderr == "warning: 2 problems in the context tree; run 'idion check'\n"


def test_problems_outside_the_prefix_are_not_reported(runner, root):
    (root / "notes.txt").write_text("x")
    assert runner.invoke(main, ["list", "teams/"]).stderr == ""


@pytest.mark.parametrize("depth", ["0", "-1", "x"])
def test_invalid_depth(runner, root, depth):
    assert runner.invoke(main, ["list", "--depth", depth]).exit_code == 2


@pytest.mark.parametrize(
    ("prefix", "message"),
    [("missing/", "no folder 'missing/'"), ("teams", "did you mean 'teams/'"), ("../", "not allowed")],
)
def test_invalid_prefix(runner, root, prefix, message):
    result = runner.invoke(main, ["list", prefix])
    assert result.exit_code == 1
    assert message in result.stderr


def test_missing_root(runner, home):
    result = runner.invoke(main, ["list"])
    assert result.exit_code == 1
    assert "idion init" in result.stderr
