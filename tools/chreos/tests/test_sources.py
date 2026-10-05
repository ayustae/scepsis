import pytest

from chreos.errors import ChreosError
from chreos.model import SourceType
from chreos.sources import Source, check_source_change, require_source, resolve, source_warnings

GIT, LOCAL = SourceType.GIT, SourceType.LOCAL


@pytest.fixture
def bases(tmp_path):
    code, files = tmp_path / "code", tmp_path / "files"
    code.mkdir()
    files.mkdir()
    return {GIT: code, LOCAL: files}


class TestSource:
    def test_from_meta(self):
        assert Source.from_meta({"type": "git", "path": "x"}) == Source(GIT, "x")
        assert Source.from_meta(None) is None

    @pytest.mark.parametrize("value", ["x", {"type": "svn", "path": "x"}, {"type": "git"}, {"type": "git", "path": ""}])
    def test_invalid(self, value):
        with pytest.raises(ChreosError, match="invalid source"):
            Source.from_meta(value)


class TestResolve:
    def test_absolute(self, tmp_path, bases):
        assert resolve(Source(LOCAL, str(tmp_path)), bases) == tmp_path

    def test_tilde(self, tmp_path, monkeypatch, bases):
        monkeypatch.setenv("HOME", str(tmp_path))
        assert resolve(Source(LOCAL, "~/files"), bases) == tmp_path / "files"

    def test_relative_uses_the_base_of_its_type(self, bases):
        assert resolve(Source(GIT, "site"), bases) == bases[GIT] / "site"
        assert resolve(Source(LOCAL, "docs/x"), bases) == bases[LOCAL] / "docs" / "x"

    def test_relative_without_base(self):
        with pytest.raises(ChreosError, match="source.git_path"):
            resolve(Source(GIT, "site"), {GIT: None, LOCAL: None})
        with pytest.raises(ChreosError, match="source.local_path"):
            resolve(Source(LOCAL, "x"), {})


class TestWarningsAndRequire:
    def test_valid_local(self, bases):
        (bases[LOCAL] / "docs").mkdir()
        source = Source(LOCAL, "docs")
        assert source_warnings(source, bases) == []
        meta = {"source": {"type": "local", "path": "docs"}}
        assert require_source(meta, bases) == (source, bases[LOCAL] / "docs", None)

    def test_valid_git_finds_repository_root(self, git_repo, bases):
        (git_repo / "sub").mkdir()
        meta = {"source": {"type": "git", "path": str(git_repo / "sub")}}
        source, resolved, repo = require_source(meta, bases)
        assert resolved == git_repo / "sub"
        assert repo == git_repo
        assert source_warnings(source, bases) == []

    def test_missing_directory(self, bases):
        source = Source(LOCAL, "nope")
        assert "does not exist" in source_warnings(source, bases)[0]
        with pytest.raises(ChreosError, match="does not exist"):
            require_source({"source": {"type": "local", "path": "nope"}}, bases)

    def test_not_a_git_repository(self, bases, git_env):
        source = Source(GIT, str(bases[LOCAL]))
        assert "not inside a git repository" in source_warnings(source, bases)[0]
        with pytest.raises(ChreosError, match="not inside a git repository"):
            require_source({"source": {"type": "git", "path": str(bases[LOCAL])}}, bases)

    def test_unresolvable_is_a_warning(self):
        assert "source.git_path" in source_warnings(Source(GIT, "x"), {})[0]

    def test_no_source(self, bases):
        with pytest.raises(ChreosError, match="has no source"):
            require_source({"source": None}, bases)
        with pytest.raises(ChreosError, match="has no source"):
            require_source({}, bases)


def test_source_cannot_change_on_open_tasks():
    check_source_change("closed")
    with pytest.raises(ChreosError, match="close it first"):
        check_source_change("open")
