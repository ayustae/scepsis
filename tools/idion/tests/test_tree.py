import os

import pytest

from idion.identifiers import parse_identifier
from idion.tree import scan


class TreeBuilder:
    """Writes context files and other entries into a temporary root."""

    def __init__(self, root):
        self.root = root

    def file(self, rel, description="A description.", text=None):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if text is None:
            text = f"---\ndescription: {description}\n---\n\n# {path.stem}\n"
        path.write_text(text, encoding="utf-8")
        return path

    def folder(self, rel):
        path = self.root / rel
        path.mkdir(parents=True, exist_ok=True)
        return path


@pytest.fixture
def root(tmp_path):
    path = tmp_path / "context"
    path.mkdir()
    return path


@pytest.fixture
def build(root):
    return TreeBuilder(root)


def ids(entries):
    return [str(entry.id) for entry in entries]


def only_finding(tree):
    assert len(tree.findings) == 1, tree.findings
    return tree.findings[0]


def test_empty_root(root):
    tree = scan(root)
    assert (tree.files, tree.folders, tree.findings) == ([], [], [])
    assert tree.root == root


def test_design_example_tree(root, build):
    build.file("user.md", "The user.")
    build.file("teams/_index.md", "My team and the others.")
    build.file("teams/my-team.md", "My team.")
    build.file("teams/data-platform.md", "Data Platform.")
    build.file("company/_index.md", "Company references.")
    build.file("company/projects/_index.md", "Projects.")
    build.file("company/projects/atlas/_index.md", "Atlas.")
    build.file("company/projects/atlas/architecture.md", "Atlas architecture.")
    build.file("company/projects/atlas/runbooks.md", "Atlas runbooks.")
    tree = scan(root)
    assert tree.findings == []
    assert ids(tree.files) == [
        "company/projects/atlas/architecture",
        "company/projects/atlas/runbooks",
        "teams/data-platform",
        "teams/my-team",
        "user",
    ]
    assert ids(tree.folders) == ["company/", "company/projects/", "company/projects/atlas/", "teams/"]
    user = tree.files[-1]
    assert user.id == parse_identifier("user")
    assert user.path == root / "user.md"
    assert user.description == "The user."
    assert user.meta["description"] == "The user."
    teams = tree.folders[-1]
    assert teams.path == root / "teams"
    assert teams.description == "My team and the others."
    assert teams.index.path == root / "teams" / "_index.md"


def test_dot_entries_are_ignored_silently(root, build):
    (root / ".idion.lock").write_text("")
    build.file(".git/config", text="x")
    build.file(".hidden.md")
    build.file("user.md")
    tree = scan(root)
    assert ids(tree.files) == ["user"]
    assert tree.findings == []


def test_symlinks_are_warned_and_not_followed(tmp_path, root, build):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("---\ndescription: s\n---\n")
    (root / "linked").symlink_to(outside, target_is_directory=True)
    (root / "user.md").symlink_to(outside / "secret.md")
    tree = scan(root)
    assert tree.files == [] and tree.folders == []
    assert sorted((f.severity, f.path, f.message) for f in tree.findings) == [
        ("warning", root / "linked", "symbolic link, ignored"),
        ("warning", root / "user.md", "symbolic link, ignored"),
    ]


def test_non_markdown_files_are_warned(root, build):
    build.file("notes.txt", text="x")
    build.file("user.md")
    finding = only_finding(scan(root))
    assert finding.severity == "warning"
    assert finding.path == root / "notes.txt"
    assert "not a context file" in finding.message


def test_invalid_folder_name_is_an_error_and_its_subtree_is_skipped(root, build):
    build.file("My Team/member.md")
    build.file("user.md")
    tree = scan(root)
    assert ids(tree.files) == ["user"]
    finding = only_finding(tree)
    assert finding.severity == "error"
    assert finding.path == root / "My Team"
    assert "invalid name" in finding.message


@pytest.mark.parametrize("name", ["My File.md", "_notes.md", "a--b.md", "x.MD.md"])
def test_invalid_file_name_is_an_error(root, build, name):
    build.file(name)
    tree = scan(root)
    assert tree.files == []
    finding = only_finding(tree)
    assert (finding.severity, finding.path) == ("error", root / name)
    assert "invalid name" in finding.message


def test_root_index_is_an_error(root, build):
    build.file("_index.md")
    tree = scan(root)
    finding = only_finding(tree)
    assert finding.severity == "error"
    assert "root may not have an _index.md" in finding.message


def test_too_deep_folder_is_an_error(root, build):
    deep = "/".join(["a"] * 8)
    build.file(f"{deep}/ok.md")
    build.file(f"{deep}/b/too-deep.md")
    tree = scan(root)
    assert ids(tree.files) == [f"{deep}/ok"]
    errors = [f for f in tree.findings if f.severity == "error"]
    assert len(errors) == 1
    assert errors[0].path == root / deep / "b"
    assert "nested too deeply" in errors[0].message


def test_unparseable_file_is_listed_with_an_error(root, build):
    build.file("user.md", text="no frontmatter\n")
    build.file("other.md")
    tree = scan(root)
    assert ids(tree.files) == ["other", "user"]
    user = tree.files[1]
    assert user.meta is None and user.description is None
    finding = only_finding(tree)
    assert (finding.severity, finding.id) == ("error", "user")
    assert "no frontmatter" in finding.message


def test_non_utf8_file_is_an_error(root):
    (root / "user.md").write_bytes(b"---\ndescription: \xff\n---\n")
    finding = only_finding(scan(root))
    assert (finding.severity, finding.id) == ("error", "user")
    assert "UTF-8" in finding.message


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("---\nother: x\n---\n", "description is missing"),
        ("---\ndescription: 42\n---\n", "description must be text"),
        ("---\ndescription: ''\n---\n", "description is empty"),
    ],
)
def test_invalid_description_is_an_error(root, build, text, message):
    build.file("user.md", text=text)
    tree = scan(root)
    assert tree.files[0].description is None
    assert tree.files[0].meta is not None
    finding = only_finding(tree)
    assert (finding.severity, finding.id, finding.message) == ("error", "user", message)


def test_invalid_folder_description_is_an_error(root, build):
    build.file("teams/_index.md", text="---\nother: x\n---\n")
    build.file("teams/my-team.md")
    tree = scan(root)
    assert tree.folders[0].description is None
    assert tree.folders[0].index is not None
    finding = only_finding(tree)
    assert (finding.severity, finding.id) == ("error", "teams/")
    assert finding.path == root / "teams" / "_index.md"


def test_empty_folder_is_a_warning(root, build):
    build.folder("teams")
    tree = scan(root)
    assert ids(tree.folders) == ["teams/"]
    finding = only_finding(tree)
    assert (finding.severity, finding.id, finding.message) == ("warning", "teams/", "empty folder")


def test_folder_with_only_an_index_is_empty(root, build):
    build.file("teams/_index.md")
    finding = only_finding(scan(root))
    assert finding.message == "empty folder"


def test_folder_without_index_is_a_warning(root, build):
    build.file("teams/my-team.md")
    tree = scan(root)
    assert tree.folders[0].description is None and tree.folders[0].index is None
    finding = only_finding(tree)
    assert (finding.severity, finding.id) == ("warning", "teams/")
    assert "no _index.md" in finding.message


def test_folder_with_files_only_in_subfolders_needs_an_index(root, build):
    build.file("company/projects/_index.md")
    build.file("company/projects/atlas.md")
    finding = only_finding(scan(root))
    assert finding.id == "company/"
    assert "no _index.md" in finding.message


def test_file_and_folder_with_the_same_name_is_a_warning(root, build):
    build.file("atlas.md")
    build.file("atlas/_index.md")
    build.file("atlas/runbooks.md")
    tree = scan(root)
    assert ids(tree.files) == ["atlas", "atlas/runbooks"]
    finding = only_finding(tree)
    assert (finding.severity, finding.id) == ("warning", "atlas")
    assert "share the name" in finding.message


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read anything")
def test_unreadable_folder_is_an_error_and_the_scan_goes_on(root, build):
    locked = build.folder("locked")
    build.file("user.md")
    locked.chmod(0)
    try:
        tree = scan(root)
    finally:
        locked.chmod(0o755)
    assert ids(tree.files) == ["user"]
    errors = [f for f in tree.findings if f.severity == "error"]
    assert len(errors) == 1
    assert errors[0].path == locked
    assert "cannot read" in errors[0].message


def test_messages_do_not_repeat_the_path(root, build):
    build.file("user.md", text="no frontmatter\n")
    finding = only_finding(scan(root))
    assert str(root) not in finding.message
