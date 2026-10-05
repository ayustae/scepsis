import json
import sys

import pytest

from idion import cli_support
from idion.cli import main


@pytest.fixture
def root(home):
    path = home / ".scepsis" / "context"
    path.mkdir(parents=True)
    return path


def test_create_prints_the_path(runner, root):
    result = runner.invoke(main, ["create", "teams/my-team", "-d", "My team."])
    path = root / "teams" / "my-team.md"
    assert result.exit_code == 0, result.output
    assert result.output == f"{path}\n"
    assert path.read_text() == "---\ndescription: My team.\n---\n\n# my-team\n"


def test_create_strips_the_description(runner, root):
    assert runner.invoke(main, ["create", "user", "-d", "  The user.  "]).exit_code == 0
    assert "description: The user.\n" in (root / "user.md").read_text()


@pytest.mark.parametrize(
    ("args", "stdin", "body"),
    [
        (["-b", "# Me"], None, "# Me\n"),
        (["--body", "-"], "# Piped\n\nText.\n", "# Piped\n\nText.\n"),
    ],
)
def test_create_with_a_body(runner, root, args, stdin, body):
    result = runner.invoke(main, ["create", "user", "-d", "The user.", *args], input=stdin)
    assert result.exit_code == 0, result.output
    assert (root / "user.md").read_text() == f"---\ndescription: The user.\n---\n\n{body}"


def test_create_with_a_body_file(runner, root, tmp_path):
    body = tmp_path / "body.md"
    body.write_text("# From a file\n")
    result = runner.invoke(main, ["create", "user", "-d", "The user.", "--body-file", str(body)])
    assert result.exit_code == 0, result.output
    assert (root / "user.md").read_text().endswith("\n# From a file\n")


def test_body_and_body_file_exclude_each_other(runner, root, tmp_path):
    body = tmp_path / "body.md"
    body.write_text("x")
    result = runner.invoke(main, ["create", "user", "-d", "x", "-b", "y", "--body-file", str(body)])
    assert result.exit_code == 2
    assert not (root / "user.md").exists()


def test_description_is_required(runner, root):
    assert runner.invoke(main, ["create", "user"]).exit_code == 2


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["User", "-d", "x"], "invalid segment"),
        (["teams/", "-d", "x"], "is a folder"),
        (["../x", "-d", "x"], "not allowed"),
        (["user", "-d", "two\nlines"], "single line"),
        (["user", "-d", "   "], "empty"),
        (["user", "-d", "x", "-b", "a\0b"], "NUL"),
    ],
)
def test_invalid_input_writes_nothing(runner, root, args, message):
    result = runner.invoke(main, ["create", *args])
    assert result.exit_code == 1
    assert message in result.stderr
    assert list(root.iterdir()) == []


def test_existing_file_is_an_error(runner, root):
    (root / "user.md").write_text("mine")
    result = runner.invoke(main, ["create", "user", "-d", "x"])
    assert result.exit_code == 1
    assert "already exists" in result.stderr
    assert (root / "user.md").read_text() == "mine"


def test_missing_root_asks_for_init(runner, home):
    result = runner.invoke(main, ["create", "user", "-d", "x"])
    assert result.exit_code == 1
    assert "run 'idion init' first" in result.stderr


class TestShow:
    def test_text_is_the_raw_file(self, runner, root):
        text = "---\r\ndescription: x  # note\r\n---\r\n\r\n# U\todd   spacing\r\n"
        (root / "user.md").write_bytes(text.encode())
        result = runner.invoke(main, ["show", "user"])
        assert result.exit_code == 0
        assert result.stdout_bytes == text.encode()  # `stdout` would turn CRLF into LF
        assert result.stderr == ""

    def test_json(self, runner, root):
        runner.invoke(main, ["create", "teams/my-team", "-d", "My team."])
        result = runner.invoke(main, ["show", "teams/my-team", "--json"])
        assert result.exit_code == 0
        assert json.loads(result.stdout) == {
            "id": "teams/my-team",
            "path": str(root / "teams" / "my-team.md"),
            "frontmatter": {"description": "My team."},
            "body": "\n# my-team\n",
            "problems": [],
        }

    def test_broken_file_is_shown_with_a_warning(self, runner, root):
        (root / "user.md").write_text("no frontmatter here\n")
        result = runner.invoke(main, ["show", "user"])
        assert result.exit_code == 0
        assert result.stdout == "no frontmatter here\n"
        assert result.stderr.startswith("warning: ")

    def test_broken_file_json(self, runner, root):
        (root / "user.md").write_text("no frontmatter here\n")
        data = json.loads(runner.invoke(main, ["show", "user", "--json"]).stdout)
        assert data["frontmatter"] is None
        assert data["body"] == "no frontmatter here\n"
        assert len(data["problems"]) == 1

    def test_invalid_description_is_a_warning(self, runner, root):
        (root / "user.md").write_text("---\ndescription: ''\n---\n")
        result = runner.invoke(main, ["show", "user"])
        assert result.exit_code == 0
        assert result.stderr == "warning: description is empty\n"

    @pytest.mark.parametrize(
        ("identifier", "message"),
        [("user", "no context file 'user'"), ("teams/", "is a folder"), ("User", "invalid segment")],
    )
    def test_errors(self, runner, root, identifier, message):
        result = runner.invoke(main, ["show", identifier])
        assert result.exit_code == 1
        assert message in result.stderr

    def test_missing_root(self, runner, home):
        result = runner.invoke(main, ["show", "user"])
        assert result.exit_code == 1
        assert "idion init" in result.stderr


class TestUpdate:
    def test_prints_the_path(self, runner, root):
        runner.invoke(main, ["create", "user", "-d", "Old."])
        result = runner.invoke(main, ["update", "user", "-d", "  New.  "])
        assert result.exit_code == 0
        assert result.stdout == f"{root / 'user.md'}\n"
        assert (root / "user.md").read_text() == "---\ndescription: New.\n---\n\n# user\n"

    @pytest.mark.parametrize(
        ("args", "message"),
        [
            (["user", "-d", ""], "empty"),
            (["other", "-d", "x"], "no context file"),
            (["teams/", "-d", "x"], "is a folder"),
        ],
    )
    def test_errors_leave_the_file_alone(self, runner, root, args, message):
        runner.invoke(main, ["create", "user", "-d", "Old."])
        before = (root / "user.md").read_text()
        result = runner.invoke(main, ["update", *args])
        assert result.exit_code == 1
        assert message in result.stderr
        assert (root / "user.md").read_text() == before

    def test_description_is_required(self, runner, root):
        assert runner.invoke(main, ["update", "user"]).exit_code == 2


class TestAppend:
    def test_text_and_stdin(self, runner, root):
        runner.invoke(main, ["create", "user", "-d", "The user."])
        first = runner.invoke(main, ["append", "user", "-t", "Prefers short answers."])
        second = runner.invoke(main, ["append", "user", "-t", "-"], input="Works in CET.\nUses vim.\n")
        assert (first.exit_code, second.exit_code) == (0, 0)
        assert first.stdout == f"{root / 'user.md'}\n"
        assert (root / "user.md").read_text() == (
            "---\ndescription: The user.\n---\n\n# user\n\nPrefers short answers.\n\nWorks in CET.\nUses vim.\n"
        )

    def test_empty_text_is_an_error(self, runner, root):
        runner.invoke(main, ["create", "user", "-d", "The user."])
        result = runner.invoke(main, ["append", "user", "-t", "  "])
        assert result.exit_code == 1
        assert "empty" in result.stderr

    def test_invalid_description_warns(self, runner, root):
        (root / "user.md").write_text("---\nowner: me\n---\n")
        result = runner.invoke(main, ["append", "user", "-t", "x"])
        assert result.exit_code == 0
        assert result.stderr == "warning: description is missing\n"

    def test_text_is_required(self, runner, root):
        assert runner.invoke(main, ["append", "user"]).exit_code == 2

    def test_missing_root(self, runner, home):
        result = runner.invoke(main, ["append", "user", "-t", "x"])
        assert result.exit_code == 1
        assert "idion init" in result.stderr


class TestEdit:
    @pytest.fixture(autouse=True)
    def terminal(self, monkeypatch):
        monkeypatch.setattr(cli_support, "is_interactive", lambda: True)

    @pytest.fixture
    def set_editor(self, tmp_path, monkeypatch):
        def set_editor(script):
            path = tmp_path / "fake_editor.py"
            path.write_text("import sys, pathlib\np = pathlib.Path(sys.argv[1])\n" + script)
            monkeypatch.setenv("EDITOR", f"{sys.executable} {path}")
            monkeypatch.delenv("VISUAL", raising=False)

        return set_editor

    def test_edits_a_file(self, runner, root, set_editor):
        runner.invoke(main, ["create", "user", "-d", "The user."])
        set_editor("p.write_text(p.read_text().replace('The user.', 'Edited.'))")
        result = runner.invoke(main, ["edit", "user"])
        assert (result.exit_code, result.output) == (0, "")
        assert "description: Edited." in (root / "user.md").read_text()

    def test_edits_a_folder_index(self, runner, root, set_editor):
        runner.invoke(main, ["folder", "describe", "teams/", "-d", "Teams."])
        set_editor("p.write_text(p.read_text().replace('Teams.', 'All teams.'))")
        assert runner.invoke(main, ["edit", "teams/"]).exit_code == 0
        assert "All teams." in (root / "teams" / "_index.md").read_text()

    def test_broken_result_is_an_error(self, runner, root, set_editor):
        runner.invoke(main, ["create", "user", "-d", "The user."])
        set_editor("p.write_text('junk\\n')")
        result = runner.invoke(main, ["edit", "user"])
        assert result.exit_code == 1
        assert "left as saved" in result.stderr
        assert (root / "user.md").read_text() == "junk\n"

    def test_invalid_description_is_an_error(self, runner, root, set_editor):
        runner.invoke(main, ["create", "user", "-d", "The user."])
        set_editor("p.write_text(p.read_text().replace('description: The user.', 'other: x'))")
        result = runner.invoke(main, ["edit", "user"])
        assert result.exit_code == 1
        assert "description is missing" in result.stderr

    def test_unchanged_broken_file_warns(self, runner, root, set_editor):
        (root / "user.md").write_text("junk\n")
        set_editor("")
        result = runner.invoke(main, ["edit", "user"])
        assert result.exit_code == 0
        assert result.stderr.startswith("warning: ")

    def test_no_terminal_gives_the_path(self, runner, root, monkeypatch):
        runner.invoke(main, ["create", "user", "-d", "The user."])
        monkeypatch.setattr(cli_support, "is_interactive", lambda: False)
        result = runner.invoke(main, ["edit", "user"])
        assert result.exit_code == 1
        assert f"edit needs a terminal; edit the file directly: {root / 'user.md'}" in result.stderr

    @pytest.mark.parametrize(
        ("identifier", "message"),
        [("user", "no context file"), ("/", "the root has no description"), ("teams/", "no folder")],
    )
    def test_errors(self, runner, root, identifier, message):
        result = runner.invoke(main, ["edit", identifier])
        assert result.exit_code == 1
        assert message in result.stderr

    def test_missing_root(self, runner, home):
        result = runner.invoke(main, ["edit", "user"])
        assert result.exit_code == 1
        assert "idion init" in result.stderr


class TestMoveCommand:
    def test_move_prints_the_new_path(self, runner, root):
        runner.invoke(main, ["create", "teams/my-team", "-d", "My team."])
        result = runner.invoke(main, ["move", "teams/my-team", "people/my-team"])
        assert result.exit_code == 0, result.output
        assert result.stdout == f"{root / 'people' / 'my-team.md'}\n"
        assert runner.invoke(main, ["list"]).stdout == "people/my-team — My team.\n"

    def test_move_errors(self, runner, root):
        result = runner.invoke(main, ["move", "user", "people/"])
        assert result.exit_code == 1
        assert "is a folder" in result.stderr


class TestDeleteCommand:
    def test_force(self, runner, root):
        runner.invoke(main, ["create", "user", "-d", "The user."])
        result = runner.invoke(main, ["delete", "user", "-f"])
        assert (result.exit_code, result.stdout) == (0, f"Deleted {root / 'user.md'}\n")
        assert not (root / "user.md").exists()

    def test_without_a_terminal_it_needs_force(self, runner, root, monkeypatch):
        monkeypatch.setattr(cli_support, "is_interactive", lambda: False)
        runner.invoke(main, ["create", "user", "-d", "The user."])
        result = runner.invoke(main, ["delete", "user"])
        assert result.exit_code == 1
        assert "confirmation required: run in a terminal or pass -f" in result.stderr
        assert (root / "user.md").exists()

    @pytest.mark.parametrize(("answer", "code", "exists"), [("y\n", 0, False), ("n\n", 1, True)])
    def test_asks_on_a_terminal(self, runner, root, monkeypatch, answer, code, exists):
        monkeypatch.setattr(cli_support, "is_interactive", lambda: True)
        runner.invoke(main, ["create", "user", "-d", "The user."])
        result = runner.invoke(main, ["delete", "user"], input=answer)
        assert result.exit_code == code
        assert (root / "user.md").exists() is exists

    def test_non_empty_folder_needs_force(self, runner, root):
        runner.invoke(main, ["create", "teams/my-team", "-d", "My team."])
        result = runner.invoke(main, ["delete", "teams/"])
        assert result.exit_code == 1
        assert "is not empty" in result.stderr
        assert runner.invoke(main, ["delete", "teams/", "-f"]).exit_code == 0
        assert not (root / "teams").exists()
