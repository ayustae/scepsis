import pytest

from idion.errors import IdionError
from idion.files import (
    append_text,
    appended_body,
    create_file,
    default_body,
    delete_entry,
    describe_folder,
    index_path,
    load_file,
    load_index,
    move_entry,
    replace_body,
    replaced_body,
    update_description,
)
from idion.identifiers import parse_file_id, parse_folder_id, parse_identifier
from idion.tree import scan


@pytest.fixture
def root(tmp_path):
    path = tmp_path / "context"
    path.mkdir()
    return path


def test_default_body_is_a_heading_with_the_last_segment():
    assert default_body(parse_file_id("teams/my-team")) == "# my-team"


def test_create_writes_frontmatter_and_default_body(root):
    path = create_file(root, parse_file_id("teams/my-team"), "My team.", None)
    assert path == root / "teams" / "my-team.md"
    assert path.read_text(encoding="utf-8") == "---\ndescription: My team.\n---\n\n# my-team\n"


def test_create_with_a_body(root):
    path = create_file(root, parse_file_id("user"), "The user.", "# Me\n\nHello.")
    assert path.read_text() == "---\ndescription: The user.\n---\n\n# Me\n\nHello.\n"


def test_body_keeps_its_own_trailing_newline(root):
    path = create_file(root, parse_file_id("user"), "The user.", "# Me\n")
    assert path.read_text().endswith("\n# Me\n")


def test_empty_body(root):
    path = create_file(root, parse_file_id("user"), "The user.", "")
    assert path.read_text() == "---\ndescription: The user.\n---\n"


def test_descriptions_needing_quotes_round_trip(root):
    create_file(root, parse_file_id("user"), 'Me: role # "prefs"', None)
    assert scan(root).files[0].description == 'Me: role # "prefs"'


def test_parent_folders_are_created(root):
    create_file(root, parse_file_id("company/projects/atlas/architecture"), "Atlas.", None)
    assert (root / "company" / "projects" / "atlas").is_dir()


def test_existing_file_is_not_overwritten(root):
    (root / "user.md").write_text("mine")
    with pytest.raises(IdionError, match="'user' already exists"):
        create_file(root, parse_file_id("user"), "The user.", None)
    assert (root / "user.md").read_text() == "mine"


def test_symlinked_parent_is_rejected(tmp_path, root):
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "teams").symlink_to(outside, target_is_directory=True)
    with pytest.raises(IdionError, match="symbolic link"):
        create_file(root, parse_file_id("teams/my-team"), "My team.", None)
    assert list(outside.iterdir()) == []


def test_created_files_scan_cleanly(root):
    create_file(root, parse_file_id("user"), "The user.", None)
    create_file(root, parse_file_id("teams/my-team"), "My team.", "# Team")
    tree = scan(root)
    assert [str(f.id) for f in tree.files] == ["teams/my-team", "user"]
    assert [f.message for f in tree.findings] == ["no _index.md: the folder has no description"]


class TestLoadFile:
    def test_valid_file(self, root):
        path = create_file(root, parse_file_id("user"), "The user.", None)
        loaded = load_file(root, parse_file_id("user"))
        assert loaded.id == parse_file_id("user")
        assert loaded.path == path
        assert loaded.text == path.read_text()
        assert loaded.doc.meta["description"] == "The user."
        assert loaded.problems == []

    def test_crlf_text_is_kept(self, root):
        (root / "user.md").write_bytes(b"---\r\ndescription: x\r\n---\r\n\r\n# U\r\n")
        loaded = load_file(root, parse_file_id("user"))
        assert loaded.text == "---\r\ndescription: x\r\n---\r\n\r\n# U\r\n"
        assert loaded.doc.body == "\r\n# U\r\n"

    def test_broken_frontmatter_is_a_problem(self, root):
        (root / "user.md").write_text("just text\n")
        loaded = load_file(root, parse_file_id("user"))
        assert loaded.doc is None
        assert loaded.text == "just text\n"
        assert len(loaded.problems) == 1 and "no frontmatter" in loaded.problems[0]

    def test_invalid_description_is_a_problem(self, root):
        (root / "user.md").write_text("---\nother: x\n---\n")
        loaded = load_file(root, parse_file_id("user"))
        assert loaded.doc is not None
        assert loaded.problems == ["description is missing"]

    def test_missing_file(self, root):
        with pytest.raises(IdionError, match="no context file 'user'"):
            load_file(root, parse_file_id("user"))

    def test_symlink_is_rejected(self, tmp_path, root):
        (tmp_path / "real.md").write_text("---\ndescription: x\n---\n")
        (root / "user.md").symlink_to(tmp_path / "real.md")
        with pytest.raises(IdionError, match="symbolic link"):
            load_file(root, parse_file_id("user"))

    def test_non_utf8_is_an_error(self, root):
        (root / "user.md").write_bytes(b"\xff")
        with pytest.raises(IdionError, match="not valid UTF-8"):
            load_file(root, parse_file_id("user"))


@pytest.mark.parametrize(
    ("body", "text", "newline", "expected"),
    [
        ("\n# U\n", "New.", "\n", "\n# U\n\nNew.\n"),
        ("\n# U", "New.", "\n", "\n# U\n\nNew.\n"),
        ("\n# U\n\n\n\n", "New.", "\n", "\n# U\n\nNew.\n"),
        ("", "New.", "\n", "\nNew.\n"),
        ("\n\n", "New.", "\n", "\nNew.\n"),
        ("\n# U\n", "Line 1\nLine 2", "\n", "\n# U\n\nLine 1\nLine 2\n"),
        ("\r\n# U\r\n", "Line 1\nLine 2", "\r\n", "\r\n# U\r\n\r\nLine 1\r\nLine 2\r\n"),
        ("\r\n# U\r\n", "A\r\nB", "\r\n", "\r\n# U\r\n\r\nA\r\nB\r\n"),
        ("\n# U\n", "A\r\nB", "\n", "\n# U\n\nA\nB\n"),
    ],
)
def test_appended_body(body, text, newline, expected):
    assert appended_body(body, text, newline) == expected


RICH = "---\n# a comment\ndescription: Old.   # trailing\nowner: me\n---\n\nBody  stays\tas is.\n"


class TestUpdateDescription:
    def test_only_the_description_changes(self, root):
        (root / "user.md").write_text(RICH)
        path = update_description(root, parse_file_id("user"), "New: value.")
        assert path == root / "user.md"
        # The trailing comment survives; ruamel may realign the spaces before it.
        assert path.read_text() == RICH.replace("description: Old.   # trailing", "description: 'New: value.' # trailing")

    def test_repairs_a_missing_description(self, root):
        (root / "user.md").write_text("---\nowner: me\n---\n\nBody.\n")
        update_description(root, parse_file_id("user"), "Fixed.")
        assert scan(root).files[0].description == "Fixed."
        assert (root / "user.md").read_text().endswith("\n---\n\nBody.\n")

    def test_unchanged_description_is_not_rewritten(self, root):
        (root / "user.md").write_text("---\ndescription: Same.\n---\n")
        before = (root / "user.md").stat()
        update_description(root, parse_file_id("user"), "Same.")
        after = (root / "user.md").stat()
        assert (before.st_ino, before.st_mtime_ns) == (after.st_ino, after.st_mtime_ns)

    def test_broken_frontmatter_is_refused(self, root):
        (root / "user.md").write_text("no frontmatter\n")
        with pytest.raises(IdionError, match="can't be parsed.*idion edit"):
            update_description(root, parse_file_id("user"), "New.")
        assert (root / "user.md").read_text() == "no frontmatter\n"

    def test_missing_file(self, root):
        with pytest.raises(IdionError, match="no context file"):
            update_description(root, parse_file_id("user"), "New.")


class TestAppendText:
    def test_appends_a_paragraph(self, root):
        (root / "user.md").write_text(RICH)
        path, problems = append_text(root, parse_file_id("user"), "More.")
        assert problems == []
        assert path.read_text() == RICH + "\nMore.\n"

    def test_keeps_crlf(self, root):
        (root / "user.md").write_bytes(b"---\r\ndescription: x\r\n---\r\n\r\n# U\r\n")
        append_text(root, parse_file_id("user"), "A\nB")
        assert (root / "user.md").read_bytes() == b"---\r\ndescription: x\r\n---\r\n\r\n# U\r\n\r\nA\r\nB\r\n"

    def test_broken_frontmatter_is_refused(self, root):
        (root / "user.md").write_text("no frontmatter\n")
        with pytest.raises(IdionError, match="can't be parsed"):
            append_text(root, parse_file_id("user"), "More.")
        assert (root / "user.md").read_text() == "no frontmatter\n"

    def test_invalid_description_is_reported_but_allowed(self, root):
        (root / "user.md").write_text("---\nowner: me\n---\n")
        path, problems = append_text(root, parse_file_id("user"), "More.")
        assert problems == ["description is missing"]
        assert path.read_text() == "---\nowner: me\n---\n\nMore.\n"


@pytest.mark.parametrize(
    ("text", "newline", "expected"),
    [
        ("# New", "\n", "\n# New\n"),
        ("# New\n", "\n", "\n# New\n"),
        ("A\nB", "\n", "\nA\nB\n"),
        ("A\r\nB", "\n", "\nA\nB\n"),
        ("A\nB", "\r\n", "\r\nA\r\nB\r\n"),
        ("", "\n", ""),
    ],
)
def test_replaced_body(text, newline, expected):
    assert replaced_body(text, newline) == expected


class TestReplaceBody:
    def test_only_the_body_changes(self, root):
        (root / "user.md").write_text(RICH)
        path, problems = replace_body(root, parse_file_id("user"), "# New\n\nText.")
        assert problems == []
        assert path.read_text() == RICH.split("---\n\n")[0] + "---\n\n# New\n\nText.\n"

    def test_empty_text_clears_the_body(self, root):
        (root / "user.md").write_text("---\ndescription: x\n---\n\n# U\n")
        replace_body(root, parse_file_id("user"), "")
        assert (root / "user.md").read_text() == "---\ndescription: x\n---\n"

    def test_keeps_crlf(self, root):
        (root / "user.md").write_bytes(b"---\r\ndescription: x\r\n---\r\n\r\n# U\r\n")
        replace_body(root, parse_file_id("user"), "A\nB")
        assert (root / "user.md").read_bytes() == b"---\r\ndescription: x\r\n---\r\n\r\nA\r\nB\r\n"

    def test_unchanged_body_is_not_rewritten(self, root):
        (root / "user.md").write_text("---\ndescription: x\n---\n\n# U\n")
        before = (root / "user.md").stat()
        replace_body(root, parse_file_id("user"), "# U")
        after = (root / "user.md").stat()
        assert (before.st_ino, before.st_mtime_ns) == (after.st_ino, after.st_mtime_ns)

    def test_broken_frontmatter_is_refused(self, root):
        (root / "user.md").write_text("no frontmatter\n")
        with pytest.raises(IdionError, match="can't be parsed"):
            replace_body(root, parse_file_id("user"), "New.")
        assert (root / "user.md").read_text() == "no frontmatter\n"

    def test_invalid_description_is_reported_but_allowed(self, root):
        (root / "user.md").write_text("---\nowner: me\n---\n\nOld.\n")
        path, problems = replace_body(root, parse_file_id("user"), "New.")
        assert problems == ["description is missing"]
        assert path.read_text() == "---\nowner: me\n---\n\nNew.\n"

    def test_missing_file(self, root):
        with pytest.raises(IdionError, match="no context file"):
            replace_body(root, parse_file_id("user"), "New.")


class TestFolderIndex:
    def test_index_path(self, root):
        assert index_path(root, parse_folder_id("teams/")) == root / "teams" / "_index.md"

    def test_root_has_no_index(self, root):
        with pytest.raises(IdionError, match="the root has no description"):
            index_path(root, parse_folder_id("/"))

    def test_symlinked_index_is_refused(self, tmp_path, root):
        (root / "teams").mkdir()
        (tmp_path / "real.md").write_text("---\ndescription: x\n---\n")
        (root / "teams" / "_index.md").symlink_to(tmp_path / "real.md")
        with pytest.raises(IdionError, match="symbolic link"):
            index_path(root, parse_folder_id("teams/"))

    def test_describe_creates_folder_and_index(self, root):
        path = describe_folder(root, parse_folder_id("company/projects/"), "Projects.")
        assert path == root / "company" / "projects" / "_index.md"
        assert path.read_text() == "---\ndescription: Projects.\n---\n"
        assert scan(root).folders[-1].description == "Projects."

    def test_describe_updates_only_the_description(self, root):
        (root / "teams").mkdir()
        (root / "teams" / "_index.md").write_text(RICH)
        describe_folder(root, parse_folder_id("teams/"), "New.")
        assert (root / "teams" / "_index.md").read_text() == RICH.replace("Old.   # trailing", "New.   # trailing")

    def test_unchanged_description_is_not_rewritten(self, root):
        path = describe_folder(root, parse_folder_id("teams/"), "Teams.")
        before = path.stat()
        describe_folder(root, parse_folder_id("teams/"), "Teams.")
        assert path.stat().st_mtime_ns == before.st_mtime_ns

    def test_broken_index_is_refused(self, root):
        (root / "teams").mkdir()
        (root / "teams" / "_index.md").write_text("junk\n")
        with pytest.raises(IdionError, match="can't be parsed"):
            describe_folder(root, parse_folder_id("teams/"), "New.")
        assert (root / "teams" / "_index.md").read_text() == "junk\n"

    def test_load_index(self, root):
        describe_folder(root, parse_folder_id("teams/"), "Teams.")
        loaded = load_index(root, parse_folder_id("teams/"))
        assert str(loaded.id) == "teams/"
        assert loaded.doc.meta["description"] == "Teams."
        assert loaded.problems == []

    def test_load_index_of_a_missing_folder(self, root):
        with pytest.raises(IdionError, match="no folder 'teams/'"):
            load_index(root, parse_folder_id("teams/"))

    def test_load_index_of_an_undescribed_folder(self, root):
        (root / "teams").mkdir()
        with pytest.raises(IdionError, match="'teams/' has no description.*folder describe"):
            load_index(root, parse_folder_id("teams/"))


def fid(text):
    return parse_identifier(text)


class TestMove:
    def test_moves_a_file_byte_for_byte(self, root):
        (root / "teams").mkdir()
        (root / "teams" / "my-team.md").write_bytes(RICH.encode())
        path = move_entry(root, fid("teams/my-team"), fid("people/teams/my-team"))
        assert path == root / "people" / "teams" / "my-team.md"
        assert path.read_bytes() == RICH.encode()
        assert not (root / "teams" / "my-team.md").exists()
        assert (root / "teams").is_dir()  # emptied folders are left in place

    def test_moves_a_folder_with_everything_in_it(self, root):
        create_file(root, fid("company/projects/atlas"), "Atlas.", None)
        describe_folder(root, fid("company/"), "Company.")
        path = move_entry(root, fid("company/"), fid("org/company/"))
        assert path == root / "org" / "company"
        assert (path / "_index.md").is_file()
        assert (path / "projects" / "atlas.md").is_file()
        assert not (root / "company").exists()

    @pytest.mark.parametrize(
        ("src", "dst", "message"),
        [
            ("user", "people/", "is a folder"),
            ("teams/", "people", "is a file"),
            ("/", "x/", "the root can't be moved"),
            ("teams/", "/", "the root can't be moved"),
            ("missing", "other", "no context file 'missing'"),
            ("missing/", "other/", "no folder 'missing/'"),
            ("user", "other", "'other' already exists"),
            ("teams/", "other-teams/", "'other-teams/' already exists"),
            ("teams/", "teams/sub/", "into itself"),
            ("teams/", "teams/", "into itself"),
        ],
    )
    def test_refused_moves_change_nothing(self, root, src, dst, message):
        create_file(root, fid("user"), "The user.", None)
        create_file(root, fid("other"), "Other.", None)
        create_file(root, fid("teams/my-team"), "My team.", None)
        (root / "other-teams").mkdir()
        before = sorted(p.relative_to(root) for p in root.rglob("*"))
        with pytest.raises(IdionError, match=message):
            move_entry(root, fid(src), fid(dst))
        assert sorted(p.relative_to(root) for p in root.rglob("*")) == before

    def test_symlinked_destination_parent_is_refused(self, tmp_path, root):
        create_file(root, fid("user"), "The user.", None)
        (tmp_path / "outside").mkdir()
        (root / "linked").symlink_to(tmp_path / "outside", target_is_directory=True)
        with pytest.raises(IdionError, match="symbolic link"):
            move_entry(root, fid("user"), fid("linked/user"))
        assert list((tmp_path / "outside").iterdir()) == []


def yes(message):
    return True


def no(message):
    return False


class TestDelete:
    def test_deletes_a_file_after_confirmation(self, root):
        create_file(root, fid("user"), "The user.", None)
        asked = []
        path = delete_entry(root, fid("user"), lambda m: asked.append(m) or True, force=False)
        assert path == root / "user.md" and not path.exists()
        assert asked == [f"Delete context file 'user' ({root / 'user.md'})?"]

    def test_declined_confirmation_keeps_the_file(self, root):
        create_file(root, fid("user"), "The user.", None)
        with pytest.raises(IdionError, match="cancelled"):
            delete_entry(root, fid("user"), no, force=False)
        assert (root / "user.md").exists()

    @pytest.mark.parametrize("with_index", [False, True])
    def test_deletes_an_empty_folder_after_confirmation(self, root, with_index):
        (root / "teams").mkdir()
        if with_index:
            describe_folder(root, fid("teams/"), "Teams.")
        asked = []
        delete_entry(root, fid("teams/"), lambda m: asked.append(m) or True, force=False)
        assert not (root / "teams").exists()
        assert asked == [f"Delete folder 'teams/' ({root / 'teams'})?"]

    def test_non_empty_folder_needs_force(self, root):
        create_file(root, fid("teams/my-team"), "My team.", None)
        (root / "teams" / "notes.txt").write_text("x")
        with pytest.raises(IdionError, match=r"folder 'teams/' is not empty \(2 entries\); pass -f"):
            delete_entry(root, fid("teams/"), yes, force=False)
        assert (root / "teams" / "my-team.md").exists()

    def test_force_deletes_a_folder_with_everything_in_it(self, tmp_path, root):
        create_file(root, fid("teams/sub/my-team"), "My team.", None)
        (tmp_path / "outside.md").write_text("keep me")
        (root / "teams" / "link.md").symlink_to(tmp_path / "outside.md")
        delete_entry(root, fid("teams/"), yes, force=True)
        assert not (root / "teams").exists()
        assert (tmp_path / "outside.md").read_text() == "keep me"

    @pytest.mark.parametrize(
        ("identifier", "message"),
        [("/", "the root can't be deleted"), ("missing", "no context file"), ("missing/", "no folder")],
    )
    def test_refused(self, root, identifier, message):
        with pytest.raises(IdionError, match=message):
            delete_entry(root, fid(identifier), yes, force=True)
