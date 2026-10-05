"""Thin wrapper around the git command line (design §11.2, §11.3).

git is always run with an argument list, never through a shell. Every
public function checks the git version (>= 2.30) first.
"""

import functools
import re
import subprocess
from pathlib import Path

from chreos.errors import ChreosError

MIN_VERSION = (2, 30)
VERSION = re.compile(r"git version (\d+)\.(\d+)\.(\d+)")


class GitError(ChreosError):
    pass


def run(args: list[str], cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        raise GitError("git is not installed or not on PATH") from None
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise GitError(f"git {' '.join(args)} failed: {message}")
    return result.stdout


def parse_version(text: str) -> tuple[int, int, int]:
    match = VERSION.match(text.strip())
    if match is None:
        raise GitError(f"unexpected output from 'git --version': {text.strip()!r}")
    return tuple(int(part) for part in match.groups())


def _installed_version() -> tuple[int, int, int]:
    return parse_version(run(["--version"]))


@functools.cache
def check_version() -> None:
    version = _installed_version()
    if version[:2] < MIN_VERSION:
        found = ".".join(map(str, version))
        raise GitError(f"git {found} is too old: chreos needs git >= 2.30")


def _git(args: list[str], cwd: Path) -> str:
    check_version()
    return run(args, cwd)


def toplevel(path: Path) -> Path:
    return Path(_git(["rev-parse", "--show-toplevel"], path).strip())


def is_worktree(path: Path) -> bool:
    if not (Path(path) / ".git").exists():
        return False
    try:
        top = Path(_git(["rev-parse", "--show-toplevel"], path).strip())
        return top.resolve() == Path(path).resolve()
    except GitError:
        return False


def branch_exists(repo: Path, branch: str) -> bool:
    try:
        _git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], repo)
    except GitError:
        return False
    return True


def default_base(repo: Path) -> str:
    """`origin/HEAD` when the repository has it, else `HEAD` (§11.3)."""
    try:
        _git(["show-ref", "--verify", "--quiet", "refs/remotes/origin/HEAD"], repo)
    except GitError:
        return "HEAD"
    return "origin/HEAD"


def checked_out_at(repo: Path, branch: str) -> Path | None:
    """The worktree that has `branch` checked out, if any."""
    current = None
    for line in _git(["worktree", "list", "--porcelain"], repo).splitlines():
        if line.startswith("worktree "):
            current = Path(line.removeprefix("worktree "))
        elif line == f"branch refs/heads/{branch}":
            return current
    return None


def worktree_prune(repo: Path) -> None:
    _git(["worktree", "prune"], repo)


def worktree_add(repo: Path, path: Path, branch: str, base: str) -> None:
    """Check out `branch` at `path`, creating it from `base` if it doesn't exist."""
    if base.startswith("-"):
        raise GitError(f"invalid base {base!r}")
    if branch_exists(repo, branch):
        _git(["worktree", "add", str(path), branch], repo)
    else:
        _git(["worktree", "add", "-b", branch, str(path), base], repo)


def dirty_files(worktree: Path) -> list[str]:
    """Uncommitted and untracked changes, as `XY path` lines."""
    output = _git(["status", "--porcelain", "--untracked-files=all"], worktree)
    return [line.strip() for line in output.splitlines() if line.strip()]


def _common_dir(worktree: Path) -> Path:
    common = Path(_git(["rev-parse", "--git-common-dir"], worktree).strip())
    return common if common.is_absolute() else (worktree / common).resolve()


def worktree_remove(worktree: Path, force: bool) -> None:
    """Remove a linked worktree (its branch is kept) and prune stale entries."""
    common = _common_dir(worktree)
    _git(["worktree", "remove", *(["--force"] if force else []), str(worktree)], common)
    _git(["worktree", "prune"], common)


def rename_branch(repo: Path, old: str, new: str) -> None:
    _git(["branch", "-m", old, new], repo)


def worktree_repair(worktree: Path) -> None:
    """Reconnect a worktree that was moved with its folder (e.g. by a project rename)."""
    _git(["worktree", "repair"], worktree)
