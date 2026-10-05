import subprocess
import sys
import time

import pytest

from chreos.errors import ChreosError
from chreos.lock import workspace_lock


def test_creates_lock_file_and_releases(tmp_path):
    with workspace_lock(tmp_path):
        assert (tmp_path / ".scepsis.lock").exists()
    with workspace_lock(tmp_path, timeout=0):
        pass


def test_second_writer_times_out(tmp_path):
    with workspace_lock(tmp_path):
        start = time.monotonic()
        with pytest.raises(ChreosError, match="another chreos command is writing"):
            with workspace_lock(tmp_path, timeout=0.3, poll=0.05):
                pass
        assert time.monotonic() - start >= 0.3


def test_released_on_exception(tmp_path):
    with pytest.raises(RuntimeError):
        with workspace_lock(tmp_path):
            raise RuntimeError("boom")
    with workspace_lock(tmp_path, timeout=0):
        pass


def test_waits_for_another_process(tmp_path):
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys, time\n"
            "from chreos.lock import workspace_lock\n"
            f"with workspace_lock({str(tmp_path)!r}):\n"
            "    print('locked', flush=True)\n"
            "    time.sleep(0.5)\n",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "locked"
        with pytest.raises(ChreosError):
            with workspace_lock(tmp_path, timeout=0.1, poll=0.02):
                pass
        with workspace_lock(tmp_path, timeout=5, poll=0.02):
            pass
    finally:
        holder.wait(timeout=5)
