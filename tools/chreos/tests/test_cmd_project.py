import json
import sys

import pytest

from chreos import cli_support
from chreos.config import load_config
from chreos.frontmatter import load
from conftest import run_cli as run


@pytest.fixture
def ws_root(cli_home):
    return cli_home / "ws"


def create(*args):
    result = run("project", "create", *args)
    assert result.exit_code == 0, result.output
    return result


class TestCreateUpdate:
    def test_create(self, ws_root):
        result = create("web", "-t", "Website", "-s", "Public site", "-l", "client=acme,urgent", "-l", "area=web")
        path = ws_root / "web" / "PROJECT.md"
        assert result.output.strip() == str(path)
        meta = load(path).meta
        assert (meta["title"], meta["summary"], list(meta["labels"])) == ("Website", "Public site", ["client=acme", "urgent", "area=web"])

    @pytest.mark.parametrize(("args", "code"), [(["Bad"], 1), (["default"], 1), (["x", "--status", "pending"], 2), ([], 2)])
    def test_create_errors(self, ws_root, args, code):
        assert run("project", "create", *args).exit_code == code

    def test_update_syncs_heading_and_bumps_updated(self, ws_root):
        create("web", "-s", "Old.")
        path = ws_root / "web" / "PROJECT.md"
        before = load(path).meta["updated"]
        result = run("project", "update", "web", "-t", "Website", "-s", "none", "-l", "x", "--status", "inactive")
        assert result.exit_code == 0, result.output
        doc = load(path)
        assert (doc.meta["title"], doc.meta["summary"], doc.meta["status"], list(doc.meta["labels"])) == ("Website", None, "inactive", ["x"])
        assert doc.body.startswith("\n# Website\n\n## Description")
        assert doc.meta["updated"] >= before
        assert run("project", "update", "web", "--remove-label", "x").exit_code == 0
        assert list(load(path).meta["labels"]) == []

    def test_update_warns_on_diverged_heading(self, ws_root):
        create("web")
        path = ws_root / "web" / "PROJECT.md"
        path.write_text(path.read_text().replace("# web", "# Custom"))
        result = run("project", "update", "web", "-t", "New")
        assert result.exit_code == 0
        assert "warning:" in result.stderr and "H1" in result.stderr

    def test_update_needs_an_option_and_an_existing_project(self, ws_root):
        assert run("project", "update", "default").exit_code == 2
        result = run("project", "update", "nope", "-t", "x")
        assert result.exit_code == 1 and "does not exist" in result.stderr


class TestListShowPath:
    @pytest.fixture(autouse=True)
    def projects(self, ws_root):
        create("web", "-t", "Website", "-l", "client=acme")
        create("api", "-l", "client=globex", "--status", "inactive")

    def test_default_hides_inactive(self):
        assert [line.split()[0] for line in run("project", "list").output.splitlines()] == ["default", "web"]

    def test_all_status_and_label_filters(self):
        assert "api" in run("project", "list", "--all").output
        assert run("project", "list", "--status", "inactive").output.split()[0] == "api"
        assert run("project", "list", "-l", "client=acme").output.split()[0] == "web"
        assert run("project", "list", "-t", "site").output.split()[0] == "web"

    def test_json_shape(self, ws_root):
        data = json.loads(run("project", "list", "--all", "--json", "--sort", "status").output)
        assert [entry["name"] for entry in data] == ["default", "web", "api"]
        assert data[1]["labels"] == ["client=acme"]
        assert data[1]["path"] == str(ws_root / "web" / "PROJECT.md")
        assert data[1]["created"].count("T") == 1

    def test_broken_project_file_is_a_warning(self, ws_root):
        (ws_root / "broken").mkdir()
        (ws_root / "broken" / "PROJECT.md").write_text("nope")
        result = run("project", "list")
        assert result.exit_code == 0
        assert "warning:" in result.stderr and "broken" in result.stderr

    def test_show(self, ws_root):
        path = ws_root / "web" / "PROJECT.md"
        assert run("project", "show", "web").output == path.read_text()
        data = json.loads(run("project", "show", "web", "--json").output)
        assert data["frontmatter"]["title"] == "Website" and data["path"] == str(path)
        assert run("project", "show", "nope").exit_code == 1

    def test_path(self, ws_root):
        assert run("project", "path", "web").output.strip() == str(ws_root / "web" / "PROJECT.md")


class TestDeleteRename:
    def test_delete_needs_force_without_terminal(self, ws_root):
        create("web")
        result = run("project", "delete", "web")
        assert result.exit_code == 1 and "confirmation required" in result.stderr
        assert (ws_root / "web").exists()
        assert run("project", "delete", "web", "-f").exit_code == 0
        assert not (ws_root / "web").exists()

    def test_default_project_protected(self, ws_root):
        result = run("project", "delete", "default", "-f")
        assert result.exit_code == 1 and "default project" in result.stderr

    def test_rename_default_updates_config(self, ws_root):
        result = run("project", "rename", "default", "inbox")
        assert result.exit_code == 0, result.output
        assert load_config().default_project == "inbox"
        assert (ws_root / "inbox" / "PROJECT.md").exists()


class TestDescription:
    def test_append_replace_show(self, ws_root):
        assert run("project", "description", "append", "default", "First.").exit_code == 0
        assert run("project", "description", "append", "default", input="Second\n\n### Detail\n").exit_code == 0
        assert run("project", "description", "show", "default").output == "First.\n\nSecond\n\n### Detail\n"
        assert run("project", "description", "replace", "default", "").exit_code == 0
        assert run("project", "description", "show", "default").output == ""

    def test_rejects_h2(self, ws_root):
        result = run("project", "description", "replace", "default", "## Nope")
        assert result.exit_code == 1 and "H1 or H2" in result.stderr


class TestEdit:
    def test_requires_terminal(self, ws_root):
        result = run("project", "edit", "default")
        assert result.exit_code == 1 and "terminal" in result.stderr

    def test_edit_with_errors_exits_1(self, ws_root, monkeypatch, tmp_path):
        monkeypatch.setattr(cli_support, "is_interactive", lambda: True)
        script = tmp_path / "ed.py"
        script.write_text("import sys,pathlib\np=pathlib.Path(sys.argv[1])\np.write_text(p.read_text().replace('status: active','status: bogus'))\n")
        monkeypatch.setenv("EDITOR", f"{sys.executable} {script}")
        monkeypatch.delenv("VISUAL", raising=False)
        result = run("project", "edit", "default")
        assert result.exit_code == 1 and "status" in result.stderr
