import os
import stat

import pytest

from idion import fileio
from idion.fileio import atomic_write


def test_creates_file(tmp_path):
    target = tmp_path / "a.md"
    atomic_write(target, "héllo\n")
    assert target.read_text(encoding="utf-8") == "héllo\n"


def test_replaces_file_and_leaves_no_temp_files(tmp_path):
    target = tmp_path / "a.md"
    target.write_text("old")
    atomic_write(target, "new")
    assert target.read_text() == "new"
    assert os.listdir(tmp_path) == ["a.md"]


def test_writes_text_verbatim_without_newline_translation(tmp_path):
    target = tmp_path / "a.md"
    atomic_write(target, "a\r\nb\n")
    assert target.read_bytes() == b"a\r\nb\n"


def test_preserves_existing_mode(tmp_path):
    target = tmp_path / "a.md"
    target.write_text("old")
    target.chmod(0o640)
    atomic_write(target, "new")
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_new_file_gets_default_mode(tmp_path):
    target = tmp_path / "a.md"
    atomic_write(target, "x")
    umask = os.umask(0)
    os.umask(umask)
    assert stat.S_IMODE(target.stat().st_mode) == 0o666 & ~umask


def test_failure_keeps_original_and_cleans_up(tmp_path, monkeypatch):
    target = tmp_path / "a.md"
    target.write_text("old")

    def broken_replace(src, dst):
        raise OSError("disk on fire")

    monkeypatch.setattr(fileio.os, "replace", broken_replace)
    with pytest.raises(OSError, match="disk on fire"):
        atomic_write(target, "new")
    assert target.read_text() == "old"
    assert os.listdir(tmp_path) == ["a.md"]
