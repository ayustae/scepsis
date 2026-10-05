import pytest
import tomlkit

from chreos.config import KEYS, config_path, get_value, load_config, render_new_config, set_value
from chreos.errors import ChreosError
from chreos.model import SourceType
from chreos.projects import create_project


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def configured(home):
    """A valid config pointing at an existing workspace with a default project."""
    from chreos.workspace import Workspace

    workspace = home / "ws"
    workspace.mkdir()
    create_project(Workspace(workspace), "default")
    create_project(Workspace(workspace), "other")
    write(home, render_new_config("~/ws", "default", git_path="~/code"))
    return home


def write(home, text):
    path = home / ".scepsis" / "config.toml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(text)
    return path


def test_config_path(home):
    assert config_path() == home / ".scepsis" / "config.toml"


class TestLoad:
    def test_rendered_config_loads(self, configured):
        config = load_config()
        assert config.workspace == configured / "ws"
        assert config.default_project == "default"
        assert config.bases == {SourceType.GIT: configured / "code", SourceType.LOCAL: None}
        assert config.output_format == "text"

    def test_rendered_config_documents_every_key(self, home):
        text = render_new_config("/w", "default")
        for key in KEYS:
            assert key.split(".")[1] in text
        assert "# git_path" in text  # unset optional keys appear as comments

    def test_missing_file(self, home):
        with pytest.raises(ChreosError, match="run 'chreos init'"):
            load_config()

    def test_invalid_toml(self, home):
        write(home, "[workspace\n")
        with pytest.raises(ChreosError, match="invalid TOML"):
            load_config()

    @pytest.mark.parametrize(
        ("text", "key"),
        [
            ('[defaults]\nproject = "default"\n', "workspace.path"),
            ('[workspace]\npath = "/w"\n', "defaults.project"),
            ('[workspace]\npath = "relative"\n[defaults]\nproject = "default"\n', "workspace.path"),
            ('[workspace]\npath = 3\n[defaults]\nproject = "default"\n', "workspace.path"),
            ('[workspace]\npath = "/w"\n[defaults]\nproject = "Bad"\n', "defaults.project"),
            ('[workspace]\npath = "/w"\n[defaults]\nproject = "d"\n[source]\ngit_path = "code"\n', "source.git_path"),
            ('[workspace]\npath = "/w"\n[defaults]\nproject = "d"\n[output]\nformat = "yaml"\n', "output.format"),
            ('workspace = "flat"\n[defaults]\nproject = "d"\n', "workspace.path"),
        ],
    )
    def test_invalid_values_name_the_key(self, home, text, key):
        write(home, text)
        with pytest.raises(ChreosError, match=key.replace(".", r"\.")):
            load_config()

    def test_unknown_keys_are_ignored(self, home):
        write(home, '[workspace]\npath = "/w"\nextra = 1\n[defaults]\nproject = "d"\n[future]\nx = true\n')
        assert load_config().default_project == "d"


class TestGetSet:
    def test_get(self, configured):
        assert get_value("workspace.path") == "~/ws"
        assert get_value("source.git_path") == "~/code"
        assert get_value("source.local_path") is None

    def test_unknown_key(self, configured):
        with pytest.raises(ChreosError, match="unknown key 'foo.bar'.*workspace.path"):
            get_value("foo.bar")
        with pytest.raises(ChreosError, match="unknown key"):
            set_value("foo.bar", "x")

    def test_set_keeps_comments_and_other_content(self, configured):
        path = write(configured, config_path().read_text() + "\n[future]\nx = 1  # keep me\n")
        set_value("source.local_path", "~/files")
        set_value("output.format", "json")
        text = path.read_text()
        assert "# keep me" in text and "# Root of the workspace" in text
        assert get_value("source.local_path") == "~/files"
        assert load_config().output_format == "json"

    def test_none_removes_optional_key(self, configured):
        set_value("source.git_path", "none")
        assert get_value("source.git_path") is None
        assert load_config().bases[SourceType.GIT] is None
        set_value("source.local_path", "none")  # already absent: no-op

    @pytest.mark.parametrize("key", ["workspace.path", "defaults.project"])
    def test_none_refused_for_required_keys(self, configured, key):
        with pytest.raises(ChreosError, match="required"):
            set_value(key, "none")

    @pytest.mark.parametrize(
        ("key", "value", "match"),
        [
            ("defaults.project", "missing", "no project 'missing'"),
            ("defaults.project", "Bad", "invalid name"),
            ("workspace.path", "~/nope", "does not exist"),
            ("workspace.path", "relative", "absolute"),
            ("source.git_path", "rel", "absolute"),
            ("output.format", "yaml", "text, json"),
        ],
    )
    def test_invalid_values(self, configured, key, value, match):
        before = config_path().read_text()
        with pytest.raises(ChreosError, match=match):
            set_value(key, value)
        assert config_path().read_text() == before

    def test_valid_required_values(self, configured):
        set_value("defaults.project", "other")
        (configured / "ws2").mkdir()
        set_value("workspace.path", "~/ws2")
        assert load_config().workspace == configured / "ws2"

    def test_set_creates_missing_table(self, home):
        write(home, '[workspace]\npath = "/w"\n[defaults]\nproject = "d"\n')
        set_value("output.format", "json")
        assert tomlkit.parse(config_path().read_text())["output"]["format"] == "json"
