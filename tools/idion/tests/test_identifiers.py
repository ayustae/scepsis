import pytest

from idion.errors import IdionError
from idion.identifiers import (
    ROOT,
    Identifier,
    is_valid_segment,
    parse_file_id,
    parse_folder_id,
    parse_identifier,
    resolve,
)

LONGEST = "a" * 64
DEEPEST = "/".join(["a"] * 8)


@pytest.mark.parametrize(
    ("text", "segments", "folder"),
    [
        ("user", ("user",), False),
        ("teams/my-team", ("teams", "my-team"), False),
        ("teams/", ("teams",), True),
        ("company/projects/atlas/", ("company", "projects", "atlas"), True),
        ("/", (), True),
        ("2026", ("2026",), False),
        (LONGEST, (LONGEST,), False),
        (DEEPEST, tuple(["a"] * 8), False),
        (DEEPEST + "/", tuple(["a"] * 8), True),
    ],
)
def test_valid_identifiers_are_parsed(text, segments, folder):
    identifier = parse_identifier(text)
    assert identifier == Identifier(segments, folder)
    assert str(identifier) == text


def test_root_is_a_folder_without_segments():
    assert parse_identifier("/") == ROOT
    assert ROOT.is_root and ROOT.folder
    assert not parse_identifier("teams/").is_root


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "empty"),
        ("a\0b", "control"),
        ("a\nb", "control"),
        ("a\tb", "control"),
        ("/user", "absolute"),
        ("//", "absolute"),
        ("a//b", "empty segment"),
        ("./a", r"'\.' and '\.\.'"),
        ("a/../b", r"'\.' and '\.\.'"),
        ("a/..", r"'\.' and '\.\.'"),
        ("_index", "reserved"),
        ("teams/_x/", "reserved"),
        ("user.md", r"drop the \.md extension"),
        ("teams/my-team.md", r"drop the \.md extension"),
        ("User", "invalid segment"),
        ("a b", "invalid segment"),
        ("a--b", "invalid segment"),
        ("-a", "invalid segment"),
        ("a-", "invalid segment"),
        ("a\\b", "invalid segment"),
        ("~/a", "invalid segment"),
        ("a" * 65, "invalid segment"),
        ("/".join(["a"] * 9), "at most 8"),
        ("/".join(["a"] * 9) + "/", "at most 8"),
    ],
)
def test_invalid_identifiers_are_rejected(text, message):
    with pytest.raises(IdionError, match=message):
        parse_identifier(text)


@pytest.mark.parametrize("value", [None, 1, b"user"])
def test_non_text_is_rejected(value):
    with pytest.raises(IdionError):
        parse_identifier(value)


def test_segment_validation():
    assert is_valid_segment("my-team")
    assert is_valid_segment(LONGEST)
    for name in ("", "My", "a_b", "_index", "a" * 65, "a.md", None):
        assert not is_valid_segment(name)


def test_file_id_requires_a_file():
    assert parse_file_id("teams/my-team") == Identifier(("teams", "my-team"), False)
    with pytest.raises(IdionError, match="is a folder.*'teams'"):
        parse_file_id("teams/")
    with pytest.raises(IdionError, match="is a folder"):
        parse_file_id("/")


def test_folder_id_requires_a_folder():
    assert parse_folder_id("teams/") == Identifier(("teams",), True)
    assert parse_folder_id("/") == ROOT
    with pytest.raises(IdionError, match="did you mean 'teams/'"):
        parse_folder_id("teams")


class TestResolve:
    def test_file(self, tmp_path):
        assert resolve(tmp_path, parse_identifier("teams/my-team")) == tmp_path / "teams" / "my-team.md"

    def test_folder(self, tmp_path):
        assert resolve(tmp_path, parse_identifier("teams/")) == tmp_path / "teams"

    def test_root(self, tmp_path):
        assert resolve(tmp_path, ROOT) == tmp_path

    def test_existing_entries_are_accepted(self, tmp_path):
        (tmp_path / "teams").mkdir()
        (tmp_path / "teams" / "my-team.md").write_text("x")
        assert resolve(tmp_path, parse_identifier("teams/my-team")).is_file()

    def test_symlinked_file_is_rejected(self, tmp_path):
        target = tmp_path / "real.md"
        target.write_text("x")
        (tmp_path / "user.md").symlink_to(target)
        with pytest.raises(IdionError, match="symbolic link"):
            resolve(tmp_path, parse_identifier("user"))

    @pytest.mark.parametrize("inside", [True, False])
    def test_symlinked_folder_is_rejected(self, tmp_path, inside):
        root = tmp_path / "root"
        root.mkdir()
        target = (root if inside else tmp_path) / "real"
        target.mkdir()
        (root / "teams").symlink_to(target, target_is_directory=True)
        for text in ("teams/", "teams/my-team", "teams/sub/x"):
            with pytest.raises(IdionError, match="symbolic link"):
                resolve(root, parse_identifier(text))

    def test_symlinked_root_is_accepted(self, tmp_path):
        real = tmp_path / "real"
        (real / "teams").mkdir(parents=True)
        root = tmp_path / "context"
        root.symlink_to(real, target_is_directory=True)
        assert resolve(root, parse_identifier("teams/x")) == root / "teams" / "x.md"
