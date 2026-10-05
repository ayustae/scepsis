import json

import pytest

from idion.identifiers import ROOT, parse_folder_id
from idion.listing import build_listing, findings_under
from idion.tree import scan

EXAMPLE = {
    "user.md": "The user: role, background, working preferences.",
    "teams/_index.md": "My team and the other teams in the department.",
    "teams/my-team.md": "Members, responsibilities and rituals of my team.",
    "teams/data-platform.md": "The Data Platform team: scope, contacts, channels.",
    "company/_index.md": "Company documentation references, grouped by project.",
    "company/projects/_index.md": "Projects.",
    "company/projects/atlas/_index.md": "Atlas.",
    "company/projects/atlas/architecture.md": "Atlas service architecture and dependencies.",
    "company/projects/atlas/runbooks.md": "Links to the Atlas on-call runbooks.",
}


def write(root, rel, description):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ndescription: {json.dumps(description)}\n---\n", encoding="utf-8")


@pytest.fixture
def root(tmp_path):
    path = tmp_path / "context"
    path.mkdir()
    for rel, description in EXAMPLE.items():
        write(path, rel, description)
    return path


def lines(entries):
    return [(str(e.id), e.kind, e.description, e.files) for e in entries]


def listing(root, prefix="/", **options):
    return lines(build_listing(scan(root), parse_folder_id(prefix), **options))


def test_full_listing(root):
    assert listing(root) == [
        ("company/projects/atlas/architecture", "file", "Atlas service architecture and dependencies.", None),
        ("company/projects/atlas/runbooks", "file", "Links to the Atlas on-call runbooks.", None),
        ("teams/data-platform", "file", "The Data Platform team: scope, contacts, channels.", None),
        ("teams/my-team", "file", "Members, responsibilities and rituals of my team.", None),
        ("user", "file", "The user: role, background, working preferences.", None),
    ]


def test_entries_carry_paths(root):
    entries = build_listing(scan(root), ROOT, depth=1)
    assert {str(e.id): e.path for e in entries} == {
        "company/": root / "company",
        "teams/": root / "teams",
        "user": root / "user.md",
    }


def test_depth_one(root):
    assert listing(root, depth=1) == [
        ("company/", "folder", "Company documentation references, grouped by project.", 2),
        ("teams/", "folder", "My team and the other teams in the department.", 2),
        ("user", "file", "The user: role, background, working preferences.", None),
    ]


def test_depth_two(root):
    assert listing(root, depth=2) == [
        ("company/projects/", "folder", "Projects.", 2),
        ("teams/data-platform", "file", "The Data Platform team: scope, contacts, channels.", None),
        ("teams/my-team", "file", "Members, responsibilities and rituals of my team.", None),
        ("user", "file", "The user: role, background, working preferences.", None),
    ]


def test_prefix_limits_and_keeps_full_ids(root):
    assert [line[0] for line in listing(root, "teams/")] == ["teams/data-platform", "teams/my-team"]


def test_depth_counts_from_the_prefix(root):
    assert listing(root, "company/", depth=1) == [("company/projects/", "folder", "Projects.", 2)]
    assert [line[0] for line in listing(root, "company/", depth=2)] == ["company/projects/atlas/"]
    assert [line[0] for line in listing(root, "company/", depth=3)] == [
        "company/projects/atlas/architecture",
        "company/projects/atlas/runbooks",
    ]


def test_prefix_without_files(root):
    (root / "empty").mkdir()
    assert listing(root, "empty/") == []


def test_collapsed_folder_without_description(root):
    write(root, "notes/2026/october.md", "October notes.")
    assert ("notes/", "folder", None, 1) in listing(root, depth=1)


def test_folders_adds_described_folders_that_are_not_collapsed(root):
    write(root, "loose/thing.md", "No folder description here.")
    (root / "empty").mkdir()
    write(root, "empty-described/_index.md", "Nothing inside.")
    assert listing(root, depth=2, folders=True) == [
        ("company/", "folder", "Company documentation references, grouped by project.", None),
        ("company/projects/", "folder", "Projects.", 2),
        ("loose/thing", "file", "No folder description here.", None),
        ("teams/", "folder", "My team and the other teams in the department.", None),
        ("teams/data-platform", "file", "The Data Platform team: scope, contacts, channels.", None),
        ("teams/my-team", "file", "Members, responsibilities and rituals of my team.", None),
        ("user", "file", "The user: role, background, working preferences.", None),
    ]


def test_folders_without_depth_lists_every_described_folder(root):
    ids = [line[0] for line in listing(root, folders=True) if line[1] == "folder"]
    assert ids == ["company/", "company/projects/", "company/projects/atlas/", "teams/"]


@pytest.mark.parametrize(
    ("search", "expected"),
    [
        ("my-team", ["teams/my-team"]),
        ("ON-CALL", ["company/projects/atlas/runbooks"]),
        ("atlas", ["company/projects/atlas/architecture", "company/projects/atlas/runbooks"]),
        ("nothing matches", []),
    ],
)
def test_search_on_id_and_description(root, search, expected):
    assert [line[0] for line in listing(root, search=search)] == expected


def test_search_happens_before_collapsing(root):
    assert listing(root, depth=1, search="runbooks") == [
        ("company/", "folder", "Company documentation references, grouped by project.", 1),
    ]


def test_search_removes_folders_without_matches(root):
    ids = [line[0] for line in listing(root, folders=True, search="user")]
    assert ids == ["user"]


def test_invalid_description_is_listed_as_none(root):
    (root / "broken.md").write_text("no frontmatter\n")
    write(root, "teams/_index.md", "")
    entries = listing(root, depth=1)
    assert ("broken", "file", None, None) in entries
    assert ("teams/", "folder", None, 2) in entries


def test_empty_tree(tmp_path):
    assert build_listing(scan(tmp_path), ROOT) == []


def test_findings_under(root):
    (root / "notes.txt").write_text("x")
    (root / "teams" / "stray.txt").write_text("x")
    tree = scan(root)
    assert len(findings_under(tree, root)) == 2
    assert [f.path for f in findings_under(tree, root / "teams")] == [root / "teams" / "stray.txt"]
    assert findings_under(tree, root / "company") == []
