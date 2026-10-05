import json

import pytest

from idion.cli import main


@pytest.fixture
def root(home):
    path = home / ".scepsis" / "context"
    for rel, text in {
        "user.md": "---\ndescription: The user.\n---\n\n# User\n\nWorks with the ingestion team.\n",
        "teams/_index.md": "---\ndescription: Teams.\n---\n",
        "teams/ingestion.md": "---\ndescription: Ingestion team.\n---\n\n# Ingestion\n",
    }.items():
        file = path / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
    return path


def test_text(runner, root):
    result = runner.invoke(main, ["search", "ingestion"])
    assert result.exit_code == 0, result.output
    assert result.stdout == (
        "teams/ingestion — Ingestion team.\n  5: # Ingestion\n"
        "user — The user.\n  7: Works with the ingestion team.\n"
    )
    assert result.stderr == ""


def test_json(runner, root):
    result = runner.invoke(main, ["search", "ingestion", "teams/", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [
        {
            "id": "teams/ingestion",
            "path": str(root / "teams" / "ingestion.md"),
            "description": "Ingestion team.",
            "lines": [{"line": 5, "text": "# Ingestion"}],
        }
    ]


def test_no_match_is_not_an_error(runner, root):
    result = runner.invoke(main, ["search", "nothing"])
    assert result.exit_code == 0 and result.stdout == ""


def test_problems_are_a_warning(runner, root):
    (root / "broken.md").write_text("no frontmatter, ingestion\n")
    result = runner.invoke(main, ["search", "ingestion"])
    assert result.exit_code == 0
    assert "broken — (invalid description)\n  1: no frontmatter, ingestion\n" in result.stdout
    assert result.stderr == "warning: 1 problem in the context tree; run 'idion check'\n"


@pytest.mark.parametrize(
    ("args", "code", "message"),
    [
        (["search", "  "], 1, "the search text is empty"),
        (["search", "x", "nope/"], 1, "no folder 'nope/'"),
        (["search", "x", "teams"], 1, "did you mean 'teams/'"),
        (["search"], 2, "Missing argument"),
    ],
)
def test_errors(runner, root, args, code, message):
    result = runner.invoke(main, args)
    assert result.exit_code == code
    assert message in result.stderr


def test_missing_root(runner, home):
    result = runner.invoke(main, ["search", "x"])
    assert result.exit_code == 1 and "run 'idion init' first" in result.stderr
