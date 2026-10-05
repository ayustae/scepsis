import subprocess
import sys
import time

import pytest

from idion.errors import IdionError
from idion.lock import context_lock
from idion.tree import scan


def test_creates_lock_file_and_releases(tmp_path):
    with context_lock(tmp_path):
        assert (tmp_path / ".idion.lock").exists()
    with context_lock(tmp_path, timeout=0):
        pass


def test_second_writer_times_out(tmp_path):
    with context_lock(tmp_path):
        start = time.monotonic()
        with pytest.raises(IdionError, match="another idion command is writing"):
            with context_lock(tmp_path, timeout=0.3, poll=0.05):
                pass
        assert time.monotonic() - start >= 0.3


def test_released_on_exception(tmp_path):
    with pytest.raises(RuntimeError):
        with context_lock(tmp_path):
            raise RuntimeError("boom")
    with context_lock(tmp_path, timeout=0):
        pass


def test_waits_for_another_process(tmp_path):
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys, time\n"
            "from idion.lock import context_lock\n"
            f"with context_lock({str(tmp_path)!r}):\n"
            "    print('locked', flush=True)\n"
            "    time.sleep(0.5)\n",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "locked"
        with pytest.raises(IdionError):
            with context_lock(tmp_path, timeout=0.1, poll=0.02):
                pass
        with context_lock(tmp_path, timeout=5, poll=0.02):
            pass
    finally:
        holder.wait(timeout=5)


def test_lock_file_is_not_a_context_entry(tmp_path):
    with context_lock(tmp_path):
        pass
    tree = scan(tmp_path)
    assert (tree.files, tree.folders, tree.findings) == ([], [], [])
