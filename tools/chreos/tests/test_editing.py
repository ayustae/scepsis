import sys

import pytest

from chreos.editing import edit_item, file_checks
from chreos.errors import ChreosError
from chreos.frontmatter import load
from chreos.model import Kind


def editor(tmp_path, monkeypatch, script):
    """Point $EDITOR at a Python script that edits the file given as argv[1]."""
    path = tmp_path / "fake_editor.py"
    path.write_text("import sys, pathlib\np = pathlib.Path(sys.argv[1])\n" + script)
    monkeypatch.setenv("EDITOR", f"{sys.executable} {path}")
    monkeypatch.delenv("VISUAL", raising=False)


@pytest.fixture
def project(ws):
    return ws.project("web")


def test_unchanged_file_reports_existing_problems_as_warnings(ws, project, tmp_path, monkeypatch):
    project.write_text(project.read_text().replace("# web", "# Something else"))
    before = project.read_bytes()
    editor(tmp_path, monkeypatch, "")
    result = edit_item(project, Kind.PROJECT, ws.root)
    assert not result.changed and result.errors == []
    assert any("H1" in w for w in result.warnings)
    assert project.read_bytes() == before


def test_changed_and_valid_bumps_updated(ws, project, tmp_path, monkeypatch):
    before = load(project).meta["updated"]
    editor(tmp_path, monkeypatch, "p.write_text(p.read_text().replace('# web', '# web\\n\\nEdited.'))")
    result = edit_item(project, Kind.PROJECT, ws.root)
    assert result.changed and result.errors == []
    doc = load(project)
    assert doc.meta["updated"] >= before
    assert "Edited." in doc.body


def test_changed_but_unparseable_is_left_as_saved(ws, project, tmp_path, monkeypatch):
    editor(tmp_path, monkeypatch, "p.write_text('---\\nname: [broken\\n---\\n')")
    with pytest.raises(ChreosError, match="run 'edit' again"):
        edit_item(project, Kind.PROJECT, ws.root)
    assert project.read_text() == "---\nname: [broken\n---\n"


def test_changed_with_validation_errors_still_bumps(ws, project, tmp_path, monkeypatch):
    before = load(project).meta["updated"]
    editor(tmp_path, monkeypatch, "p.write_text(p.read_text().replace('status: active', 'status: bogus'))")
    result = edit_item(project, Kind.PROJECT, ws.root)
    assert result.changed
    assert any("status" in e for e in result.errors)
    doc = load(project)
    assert doc.meta["status"] == "bogus"  # never reverted or fixed
    assert doc.meta["updated"] >= before


def test_extra_checks_hook(ws, project, tmp_path, monkeypatch):
    editor(tmp_path, monkeypatch, "")
    result = edit_item(project, Kind.PROJECT, ws.root, extra_checks=lambda doc: (["custom error"], ["custom warning"]))
    assert result.warnings[-1] == "custom warning"
    assert "custom error" in result.warnings  # unchanged file: everything is a warning


class TestFileChecks:
    def test_stale_caches_are_errors(self, ws):
        ws.project("p")
        task = ws.task("p", "t")
        task.write_text(task.read_text().replace("name: t", "name: other").replace("project: p", "project: q"))
        errors, _ = file_checks(task, Kind.TASK, load(task))
        assert any("name" in e and "'t'" in e for e in errors)
        assert any("project" in e and "'p'" in e for e in errors)

    def test_archived_and_decision_paths(self, ws):
        ws.project("p")
        for path, kind in ((ws.task("p", "a", archived=True), Kind.TASK), (ws.decision("p", "d"), Kind.DECISION)):
            assert file_checks(path, kind, load(path)) == ([], [])
