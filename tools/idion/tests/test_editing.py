import sys

import pytest

from idion.editing import edit_file
from idion.errors import IdionError
from idion.identifiers import parse_file_id


def editor(tmp_path, monkeypatch, script):
    """Point $EDITOR at a Python script that edits the file given as argv[1]."""
    path = tmp_path / "fake_editor.py"
    path.write_text("import sys, pathlib\np = pathlib.Path(sys.argv[1])\n" + script)
    monkeypatch.setenv("EDITOR", f"{sys.executable} {path}")
    monkeypatch.delenv("VISUAL", raising=False)


@pytest.fixture
def user(tmp_path):
    path = tmp_path / "user.md"
    path.write_text("---\ndescription: The user.\n---\n\n# user\n")
    return path


USER = parse_file_id("user")


def test_unchanged_valid_file(tmp_path, monkeypatch, user):
    editor(tmp_path, monkeypatch, "")
    result = edit_file(USER, user)
    assert (result.changed, result.errors, result.warnings) == (False, [], [])


def test_unchanged_broken_file_reports_warnings(tmp_path, monkeypatch, user):
    user.write_text("---\nother: x\n---\n")
    editor(tmp_path, monkeypatch, "")
    result = edit_file(USER, user)
    assert (result.changed, result.errors, result.warnings) == (False, [], ["description is missing"])
    assert user.read_text() == "---\nother: x\n---\n"


def test_changed_and_valid(tmp_path, monkeypatch, user):
    editor(tmp_path, monkeypatch, "p.write_text(p.read_text() + '\\nEdited.\\n')")
    result = edit_file(USER, user)
    assert (result.changed, result.errors, result.warnings) == (True, [], [])
    assert user.read_text().endswith("# user\n\nEdited.\n")


def test_changed_but_unparseable_is_left_as_saved(tmp_path, monkeypatch, user):
    editor(tmp_path, monkeypatch, "p.write_text('oops, no frontmatter\\n')")
    with pytest.raises(IdionError, match="no frontmatter.*\nThe file was left as saved: run 'idion edit user' again"):
        edit_file(USER, user)
    assert user.read_text() == "oops, no frontmatter\n"


def test_changed_with_an_invalid_description(tmp_path, monkeypatch, user):
    editor(tmp_path, monkeypatch, "p.write_text(p.read_text().replace('The user.', \"''\"))")
    result = edit_file(USER, user)
    assert (result.changed, result.errors) == (True, ["description is empty"])
    assert "description: ''" in user.read_text()


def test_launch_can_be_injected(user):
    seen = []
    result = edit_file(USER, user, launch=seen.append)
    assert seen == [user] and not result.changed
