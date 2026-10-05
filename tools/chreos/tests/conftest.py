from pathlib import Path

import pytest

from chreos.frontmatter import save
from chreos.model import Kind
from chreos.templates import render
from chreos.timestamps import now
from chreos.workspace import Workspace


class WorkspaceBuilder:
    """Writes real items into a temporary workspace."""

    def __init__(self, root: Path):
        self.root = root
        self.workspace = Workspace(root)

    def project(self, name: str, **fields) -> Path:
        path = self.root / name / "PROJECT.md"
        for folder in ("tasks", ".archive", "decisions"):
            (self.root / name / folder).mkdir(parents=True, exist_ok=True)
        save(path, render(Kind.PROJECT, name=name, fields=fields))
        return path

    def task(self, project, name, *, status="new", phase="closed", dependencies=(), archived=False, **fields):
        doc = render(
            Kind.TASK,
            name=name,
            project=project,
            fields={"status": status, "phase": phase, "dependencies": list(dependencies), **fields},
        )
        if archived:
            doc.meta["archived"] = now()
            path = self.root / project / ".archive" / f"{name}.md"
        else:
            path = self.root / project / "tasks" / name / "TASK.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        save(path, doc)
        return path

    def decision(self, project, name, *, status="pending", dependencies=(), **fields):
        path = self.root / project / "decisions" / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        doc = render(
            Kind.DECISION,
            name=name,
            project=project,
            fields={"status": status, "dependencies": list(dependencies), **fields},
        )
        save(path, doc)
        return path

    def write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = tmp_path / "workspace"
    root.mkdir()
    return WorkspaceBuilder(root)


def git(cwd, *args):
    import subprocess

    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def git_env(monkeypatch):
    """Isolate git from the user's configuration and give it an identity."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "test@example.com")


@pytest.fixture
def git_repo(tmp_path, git_env):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("hello\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init")
    return repo


@pytest.fixture
def cloned_repo(tmp_path, git_repo):
    """A clone of `git_repo`, so it has `origin/HEAD`."""
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(git_repo), str(clone))
    return clone


class ConfirmRecorder:
    def __init__(self, answer: bool):
        self.answer = answer
        self.messages: list[str] = []

    def __call__(self, message: str) -> bool:
        self.messages.append(message)
        return self.answer


@pytest.fixture
def yes():
    return ConfirmRecorder(True)


@pytest.fixture
def no():
    return ConfirmRecorder(False)


def run_cli(*args, input=None):
    from click.testing import CliRunner

    from chreos.cli import main

    return CliRunner().invoke(main, [str(a) for a in args], prog_name="chreos", input=input)


@pytest.fixture
def cli_home(tmp_path, monkeypatch):
    """A HOME with `chreos init` done: workspace at ~/ws, default project `default`."""
    from chreos import cli_support

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(cli_support, "is_interactive", lambda: False)
    result = run_cli("init", "--workspace-path", "~/ws")
    assert result.exit_code == 0, result.output
    return tmp_path
