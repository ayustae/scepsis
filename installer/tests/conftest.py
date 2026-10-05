import json
import stat
from pathlib import Path

import pytest


class RepoBuilder:
    """Writes a minimal Scepsis repository: skills, agents and tools."""

    def __init__(self, root: Path):
        self.root = root

    def skill(self, name, body="# Skill\n\nDo it.\n", **meta):
        meta = {"name": name, "description": f"The {name} skill.", **meta}
        return self._item("skills", "SKILL.md", name, meta, body)

    def agent(self, name, body="# Agent\n\nCheck it.\n", **meta):
        meta = {"name": name, "description": f"The {name} agent.", **meta}
        return self._item("agents", "AGENT.md", name, meta, body)

    def tool(self, name):
        folder = self.root / "tools" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n')
        return folder

    def _item(self, kind, filename, folder_name, meta, body):
        folder = self.root / kind / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / filename).write_text(body)
        (folder / "frontmatter.json").write_text(json.dumps(meta))
        return folder


@pytest.fixture
def repo(tmp_path):
    return RepoBuilder(tmp_path / "repo")


class Home(Path):
    """The test HOME; `.bin` is the only dir on PATH."""

    bin: Path


@pytest.fixture
def home(tmp_path, monkeypatch):
    """An isolated HOME, PATH holding only a fake bin dir, no assistant env vars."""
    home = Home(tmp_path / "home")
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(bin_dir))
    for var in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(var, raising=False)
    home.bin = bin_dir
    return home


def fake_command(bin_dir: Path, name: str, script: str = "exit 0") -> Path:
    """An executable `name` in `bin_dir` running the given sh script."""
    path = bin_dir / name
    path.write_text(f"#!/bin/sh\n{script}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def fake_uv(bin_dir: Path, log: Path) -> Path:
    """A fake `uv` that logs its arguments and 'installs' the tool into bin_dir.

    PATH holds only bin_dir, so it uses shell built-ins and absolute paths.
    """
    script = (
        f'echo "$@" >> "{log}"\n'
        'for last; do :; done\n'
        'name=${last##*/}\n'
        f'printf "#!/bin/sh\\nexit 0\\n" > "{bin_dir}/$name"\n'
        f'/bin/chmod +x "{bin_dir}/$name"\n'
    )
    return fake_command(bin_dir, "uv", script)


def tree(root: Path) -> dict:
    """Relative path → content of every file under root."""
    return {
        str(p.relative_to(root)): p.read_text()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }

