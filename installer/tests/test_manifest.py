import json

import install


def test_new_file_is_installed(tmp_path):
    m = install.Manifest(tmp_path / "m.json")
    assert m.decide(tmp_path / "a", "x", force=False) == "install"


def test_identical_file_is_unchanged(tmp_path):
    dest = tmp_path / "a"
    dest.write_text("x")
    m = install.Manifest(tmp_path / "m.json")
    assert m.decide(dest, "x", force=False) == "unchanged"


def test_foreign_file_is_skipped_unless_forced(tmp_path):
    dest = tmp_path / "a"
    dest.write_text("mine")
    m = install.Manifest(tmp_path / "m.json")
    assert m.decide(dest, "x", force=False) == "skip-exists"
    assert m.decide(dest, "x", force=True) == "overwrite"


def test_own_unedited_file_is_updated(tmp_path):
    dest = tmp_path / "a"
    m = install.Manifest(tmp_path / "m.json")
    install.write_file(dest, "v1")
    m.record(dest, "v1")
    assert m.decide(dest, "v2", force=False) == "update"


def test_own_file_edited_by_the_user_is_skipped_unless_forced(tmp_path):
    dest = tmp_path / "a"
    m = install.Manifest(tmp_path / "m.json")
    install.write_file(dest, "v1")
    m.record(dest, "v1")
    dest.write_text("v1 + my edits")
    assert m.decide(dest, "v2", force=False) == "skip-modified"
    assert m.decide(dest, "v2", force=True) == "overwrite"


def test_manifest_round_trip(tmp_path):
    path = tmp_path / "sub" / "m.json"
    m = install.Manifest(path)
    m.record(tmp_path / "a", "v1")
    m.save()
    data = json.loads(path.read_text())
    assert data["version"] == 1
    assert list(data["files"]) == [str(tmp_path / "a")]

    again = install.Manifest(path)
    install.write_file(tmp_path / "a", "v1")
    assert again.decide(tmp_path / "a", "v2", force=False) == "update"


def test_corrupt_manifest_protects_everything(tmp_path):
    path = tmp_path / "m.json"
    path.write_text("not json")
    dest = tmp_path / "a"
    dest.write_text("v1")
    m = install.Manifest(path)
    assert m.decide(dest, "v2", force=False) == "skip-exists"


def test_write_file_is_atomic_and_creates_parents(tmp_path):
    dest = tmp_path / "x" / "y" / "f.md"
    install.write_file(dest, "hello")
    assert dest.read_text() == "hello"
    assert [p.name for p in dest.parent.iterdir()] == ["f.md"]
