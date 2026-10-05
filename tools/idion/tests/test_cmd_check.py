import json

import pytest

from idion.cli import main


@pytest.fixture
def root(home):
    path = home / ".scepsis" / "context"
    path.mkdir(parents=True)
    return path


def write(root, rel, text="---\ndescription: x\n---\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_clean_tree(runner, root):
    write(root, "user.md")
    write(root, "teams/_index.md")
    write(root, "teams/my-team.md")
    result = runner.invoke(main, ["check"])
    assert (result.exit_code, result.output) == (0, "no problems found\n")


def test_warnings_only_exit_0(runner, root):
    write(root, "teams/my-team.md")
    write(root, "notes.txt", "x")
    result = runner.invoke(main, ["check"])
    assert result.exit_code == 0
    assert result.output == (
        "warning  notes.txt  -       not a context file, ignored\n"
        "warning  teams      teams/  no _index.md: the folder has no description\n"
        "0 errors, 2 warnings\n"
    )


def test_errors_exit_1_and_come_first(runner, root):
    write(root, "user.md", "junk\n")
    write(root, "Bad Name.md")
    write(root, "_index.md")
    write(root, "teams/my-team.md")
    result = runner.invoke(main, ["check"])
    assert result.exit_code == 1
    lines = result.output.splitlines()
    assert [line.split()[0] for line in lines[:-1]] == ["error", "error", "error", "warning"]
    assert lines[-1] == "3 errors, 1 warning"
    assert "user.md" in lines[2] and "no frontmatter" in lines[2]


def test_singular_summary(runner, root):
    write(root, "user.md", "---\nother: x\n---\n")
    write(root, "notes.txt", "x")
    result = runner.invoke(main, ["check"])
    assert result.output.splitlines()[-1] == "1 error, 1 warning"


def test_json(runner, root):
    write(root, "user.md", "---\nother: x\n---\n")
    write(root, "notes.txt", "x")
    result = runner.invoke(main, ["check", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "findings": [
            {"severity": "error", "path": str(root / "user.md"), "id": "user", "message": "description is missing"},
            {"severity": "warning", "path": str(root / "notes.txt"), "id": None, "message": "not a context file, ignored"},
        ],
        "errors": 1,
        "warnings": 1,
    }


def test_clean_json(runner, root):
    result = runner.invoke(main, ["check", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"findings": [], "errors": 0, "warnings": 0}


def test_missing_root(runner, home):
    result = runner.invoke(main, ["check"])
    assert result.exit_code == 1
    assert "idion init" in result.stderr
