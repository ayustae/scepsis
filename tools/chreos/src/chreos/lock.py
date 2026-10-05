"""Workspace lock (design §12): one writing command at a time.

An exclusive OS file lock (POSIX `flock`) on `<workspace>/.scepsis.lock`,
held for the whole command. The lock file itself is never removed: the
lock is on the open file, not on its existence, and the OS releases it if
the process dies.
"""

import fcntl
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from chreos.errors import ChreosError
from chreos.workspace import LOCK_FILE

TIMEOUT = 10.0
POLL = 0.1


@contextmanager
def workspace_lock(root: Path, timeout: float = TIMEOUT, poll: float = POLL) -> Iterator[None]:
    fd = os.open(Path(root) / LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ChreosError(
                        f"another chreos command is writing to the workspace; "
                        f"gave up after {timeout:g} s"
                    ) from None
                time.sleep(poll)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
