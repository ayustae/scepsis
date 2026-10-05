import pytest

from idion.identifiers import ROOT, parse_folder_id
from idion.search import Line, search_tree
from idion.tree import scan

FILES = {
    "user.md": "---\ndescription: The user.\n---\n\n# User\n\nPrefers short answers.\n",
    "teams/_index.md": "---\ndescription: Ingestion teams.\n---\n",
    "teams/other-team.md": (
        "---\ndescription: Other team.\n---\n\n# Other team\n\n"
        "- Owns the INGESTION pipelines.\n- Ingestion runs nightly.\n"
    ),
    "teams/ingestion.md": "---\ndescription: The ingestion squad.\n---\n\n# Squad\n",
    "company/atlas.md": "---\ndescription: Atlas.\n---\r\n\r\nNothing here.\r\nSee ingestion.\r\n",
    "broken.md": "no frontmatter\nmentions ingestion\n",
}


@pytest.fixture
def root(tmp_path):
    path = tmp_path / "context"
    for rel, text in FILES.items():
        file = path / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(text.encode())
    (path / "latin1.md").write_bytes("---\ndescription: x\n---\n\ningestion \xe9\n".encode("latin-1"))
    return path


def matches(root, text, prefix=ROOT):
    return [(str(m.id), m.lines) for m in search_tree(scan(root), prefix, text)]


def test_matches_id_description_and_body_with_file_line_numbers(root):
    assert matches(root, "ingestion") == [
        ("broken", [Line(2, "mentions ingestion")]),
        ("company/atlas", [Line(6, "See ingestion.")]),
        ("teams/ingestion", []),
        ("teams/other-team", [Line(7, "- Owns the INGESTION pipelines."), Line(8, "- Ingestion runs nightly.")]),
    ]


def test_description_only_match(root):
    assert matches(root, "the user") == [("user", [])]


def test_case_insensitive_body_match(root):
    assert matches(root, "SHORT") == [("user", [Line(7, "Prefers short answers.")])]


def test_prefix(root):
    assert [m[0] for m in matches(root, "ingestion", parse_folder_id("teams/"))] == [
        "teams/ingestion",
        "teams/other-team",
    ]


def test_match_carries_description_and_path(root):
    [match] = search_tree(scan(root), ROOT, "short")
    assert match.description == "The user." and match.path == root / "user.md"
    [broken] = search_tree(scan(root), ROOT, "mentions")
    assert broken.description is None


def test_no_match(root):
    assert matches(root, "nothing like this") == []
