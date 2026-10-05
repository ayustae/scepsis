"""Scepsis installer: installs the framework's tools, skills and agents.

Skills and agents are rendered into each AI assistant's own format. Files that
already exist are never modified unless the installer wrote them and they are
unchanged since (see `Manifest`), or `--force` is given.

Standard library only, and no POSIX-only calls, so any wrapper (sh, PowerShell)
can run it. Run with `-h` for the options.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

VERSION = "0.1.0"  # the installer's own version; keep it equal to pyproject.toml
REPO = Path(__file__).resolve().parent.parent

ASSISTANTS = ("claude", "codex", "opencode")
COMPONENTS = ("tools", "skills", "agents")
CAPABILITIES = ("read", "search", "shell", "edit", "web")
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

# Which provider's model entry each assistant uses (agents' `model` field).
PROVIDER = {"claude": "anthropic", "codex": "openai"}

CLAUDE_TOOLS = {
    "read": ["Read"],
    "search": ["Grep", "Glob"],
    "shell": ["Bash"],
    "edit": ["Edit", "Write"],
    "web": ["WebFetch", "WebSearch"],
}
OPENCODE_PERMISSIONS = {
    "read": ["read"],
    "search": ["grep", "glob", "list"],
    "shell": ["bash"],
    "edit": ["edit"],
    "web": ["webfetch", "websearch"],
}


# --- Definitions --------------------------------------------------------------


@dataclass(frozen=True)
class Item:
    """A skill or agent: its generalized frontmatter and its markdown body."""

    kind: str  # "skills" or "agents"
    name: str
    meta: dict
    body: str

    @property
    def version(self) -> str:
        return self.meta["version"]

    @property
    def label(self) -> str:
        return f"{self.kind[:-1]} {self.name}"


def _check_meta(folder: str, meta: object) -> str | None:
    """The first problem with a frontmatter, or None."""
    if not isinstance(meta, dict):
        return "frontmatter.json must hold an object"
    name = meta.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name) or len(name) > 64:
        return "invalid name (lowercase letters, digits and single hyphens, at most 64)"
    if name != folder:
        return f"name {name!r} differs from its folder name"
    if not isinstance(meta.get("description"), str) or not meta["description"].strip():
        return "missing description"
    requires = meta.get("requires", [])
    if not isinstance(requires, list) or not all(isinstance(r, str) and r for r in requires):
        return "requires must be a list of command names"
    if not isinstance(meta.get("user_invocable", True), bool):
        return "user_invocable must be true or false"
    tools = meta.get("tools", [])
    if not isinstance(tools, list) or not all(t in CAPABILITIES for t in tools):
        return f"tools must be a list of: {', '.join(CAPABILITIES)}"
    model = meta.get("model", {})
    if not isinstance(model, dict) or not all(isinstance(v, str) for v in model.values()):
        return "model must be an object of provider → model ID"
    version = meta.get("version")
    if not isinstance(version, str) or not SEMVER_RE.match(version):
        return "version must be a semantic version (MAJOR.MINOR.PATCH)"
    return None


def load_items(repo: Path, kind: str) -> tuple[list[Item], dict[str, str]]:
    """Every valid skill or agent under `repo/kind`, and the problems found by name."""
    filename = "SKILL.md" if kind == "skills" else "AGENT.md"
    items, errors = [], {}
    base = repo / kind
    if not base.is_dir():
        return items, errors
    for folder in sorted(p for p in base.iterdir() if p.is_dir()):
        body_path, meta_path = folder / filename, folder / "frontmatter.json"
        if not body_path.is_file() or not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors[folder.name] = f"unreadable frontmatter.json ({exc})"
            continue
        problem = _check_meta(folder.name, meta)
        if problem:
            errors[folder.name] = problem
            continue
        body = body_path.read_text(encoding="utf-8")
        items.append(Item(kind, folder.name, meta, body))
    return items, errors


def framework_version(repo: Path) -> str | None:
    """The Scepsis framework version, from the root VERSION file."""
    try:
        return (repo / "VERSION").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def list_tools(repo: Path) -> list[str]:
    base = repo / "tools"
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if (p / "pyproject.toml").is_file())


# --- Assistants and where things go ---------------------------------------------


@dataclass(frozen=True)
class Targets:
    skills: Path
    agents: Path


def _env_path(var: str, default: Path) -> Path:
    value = os.environ.get(var)
    return Path(value).expanduser() if value else default


def config_dirs() -> dict[str, Path]:
    """Each assistant's user config dir. The only OS-specific paths live here."""
    home = Path.home()
    xdg = _env_path("XDG_CONFIG_HOME", home / ".config")
    return {
        "claude": _env_path("CLAUDE_CONFIG_DIR", home / ".claude"),
        "codex": _env_path("CODEX_HOME", home / ".codex"),
        "opencode": xdg / "opencode",
    }


def detect_assistants() -> list[str]:
    """Assistants whose command is on PATH or whose config dir exists."""
    dirs = config_dirs()
    return [a for a in ASSISTANTS if shutil.which(a) or dirs[a].is_dir()]


def targets(
    scope: str, project_dir: Path | None = None, overrides: dict[str, Path] | None = None
) -> dict[str, Targets]:
    """Where each assistant reads skills and agents from, for a scope."""
    overrides = overrides or {}
    if scope == "project":
        p = project_dir or Path.cwd()
        dirs = {"claude": p / ".claude", "codex": p / ".codex", "opencode": p / ".opencode"}
        shared = p / ".agents" / "skills"
    else:
        dirs = config_dirs()
        shared = Path.home() / ".agents" / "skills"
    dirs.update(overrides)
    return {
        "claude": Targets(dirs["claude"] / "skills", dirs["claude"] / "agents"),
        # Codex reads skills from the cross-assistant .agents dir, not its own.
        "codex": Targets(shared, dirs["codex"] / "agents"),
        "opencode": Targets(dirs["opencode"] / "skills", dirs["opencode"] / "agents"),
    }


def opencode_shared_skill_dirs(scope: str, project_dir: Path | None = None) -> list[Path]:
    """Skill dirs OpenCode reads besides its own (Claude Code's and .agents)."""
    base = (project_dir or Path.cwd()) if scope == "project" else Path.home()
    return [base / ".claude" / "skills", base / ".agents" / "skills"]


# --- Rendering ------------------------------------------------------------------


def _yaml_str(value: str) -> str:
    # A JSON string is a valid YAML double-quoted scalar.
    return json.dumps(value, ensure_ascii=False)


def _markdown(lines: list[str], body: str) -> str:
    return "---\n" + "\n".join(lines) + "\n---\n\n" + body


def render_skill(assistant: str, item: Item) -> str:
    meta = item.meta
    lines = [f"name: {item.name}", f"description: {_yaml_str(meta['description'])}"]
    if assistant == "claude" and meta.get("user_invocable", True) is False:
        lines.append("user-invocable: false")
    return _markdown(lines, item.body)


def _model(assistant: str, model: dict) -> str | None:
    if assistant == "opencode":
        provider = model.get("default")
        return f"{provider}/{model[provider]}" if provider and provider != "default" and provider in model else None
    return model.get(PROVIDER[assistant])


def _toml_str(value: str) -> str:
    out = []
    for ch in value:
        if ch in '"\\':
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04X}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _toml_text(value: str) -> str:
    """A multi-line literal string when it can hold `value` verbatim, else a basic one."""
    literal_ok = (
        "'''" not in value
        and not value.endswith("'")
        and "\r" not in value
        and not any(ord(c) < 0x20 and c not in "\t\n" or ord(c) == 0x7F for c in value)
    )
    # The newline right after the opening delimiter is not part of the value.
    return "'''\n" + value + "'''" if literal_ok else _toml_str(value)


def render_agent(assistant: str, item: Item) -> str:
    meta = item.meta
    model = _model(assistant, meta.get("model", {}))
    tools = meta.get("tools")
    if assistant == "codex":
        lines = [f"name = {_toml_str(item.name)}", f"description = {_toml_str(meta['description'])}"]
        if model:
            lines.append(f"model = {_toml_str(model)}")
        if tools is not None:
            sandbox = "workspace-write" if "edit" in tools else "read-only"
            lines.append(f"sandbox_mode = {_toml_str(sandbox)}")
        lines.append(f"developer_instructions = {_toml_text(item.body)}")
        return "\n".join(lines) + "\n"
    if assistant == "claude":
        lines = [f"name: {item.name}", f"description: {_yaml_str(meta['description'])}"]
        if model:
            lines.append(f"model: {model}")
        if tools is not None:
            lines.append("tools: " + ", ".join(t for c in tools for t in CLAUDE_TOOLS[c]))
        return _markdown(lines, item.body)
    lines = [f"description: {_yaml_str(meta['description'])}", "mode: subagent"]
    if model:
        lines.append(f"model: {model}")
    if tools is not None:
        denied = [p for c in CAPABILITIES if c not in tools for p in OPENCODE_PERMISSIONS[c]]
        if denied:
            lines.append("permission:")
            lines.extend(f"  {p}: deny" for p in sorted(denied))
    return _markdown(lines, item.body)


def agent_filename(assistant: str, name: str) -> str:
    return f"{name}.toml" if assistant == "codex" else f"{name}.md"


# --- Writing safely ---------------------------------------------------------------


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def write_file(path: Path, content: str) -> None:
    """Write atomically: a temp file in the same dir, then a rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class Manifest:
    """The files this installer wrote: the hash of what it wrote, and which item
    and version it was.

    A file is only replaced when it is ours and unchanged since; an unreadable
    manifest makes every existing file count as foreign. Version 1 manifests
    (path → hash) are still read.
    """

    def __init__(self, path: Path):
        self.path = path
        self.files: dict[str, dict] = {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            files = data.get("files", {}) if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return
        if not isinstance(files, dict):
            return
        for dest, entry in files.items():
            if isinstance(entry, str):
                entry = {"sha256": entry}
            if isinstance(entry, dict) and isinstance(entry.get("sha256"), str):
                self.files[dest] = entry

    def decide(self, dest: Path, content: str, force: bool) -> str:
        current = _file_digest(dest)
        if current is None and not dest.exists():
            return "install"
        if current == _digest(content):
            return "unchanged"
        if force:
            return "overwrite"
        recorded = self.files.get(str(dest))
        if recorded is None:
            return "skip-exists"
        return "update" if recorded["sha256"] == current else "skip-modified"

    def record(self, dest: Path, content: str, item: str | None = None, version: str | None = None) -> None:
        entry = {"sha256": _digest(content)}
        if item:
            entry["item"] = item
        if version:
            entry["version"] = version
        self.files[str(dest)] = entry

    def save(self) -> None:
        write_file(self.path, json.dumps({"version": 2, "files": self.files}, indent=2) + "\n")


# --- Command line -------------------------------------------------------------------

LABELS = {
    "install": "install",
    "update": "update",
    "overwrite": "overwrite",
    "unchanged": "unchanged",
    "skip-exists": "skip (exists)",
    "skip-modified": "skip (modified)",
    "skip-shared": "skip (shared)",
    "skip-path": "skip (on PATH)",
}
WRITES = ("install", "update", "overwrite")


def _split(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    return [v.strip() for value in values for v in value.split(",") if v.strip()]


def _parser(framework: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="install.sh",
        description="Install the Scepsis tools, skills and agents. Existing files are "
        "never modified unless this installer wrote them and they are unchanged since.",
    )
    add = p.add_argument
    add("-a", "--assistant", action="append", metavar="LIST",
        help=f"assistants to install for: {','.join(ASSISTANTS)} (default: those detected)")
    add("-o", "--only", action="append", metavar="LIST",
        help=f"components to install: {','.join(COMPONENTS)} (default: all)")
    add("-s", "--skills", action="append", metavar="LIST", help="only these skills")
    add("-g", "--agents", action="append", metavar="LIST", help="only these agents")
    add("-t", "--tools", action="append", metavar="LIST", help="only these tools")
    add("-S", "--scope", choices=("user", "project"), default=None,
        help="user: the assistants' user config dirs (default); project: a project's dirs")
    add("-p", "--project-dir", type=Path, metavar="DIR",
        help="project to install into; implies --scope project (default: current dir)")
    add("-c", "--config-dir", action="append", default=[], metavar="ASSISTANT=DIR",
        help="override one assistant's config dir (repeatable)")
    add("-n", "--dry-run", action="store_true", help="show what would happen, write nothing")
    add("-f", "--force", action="store_true", help="overwrite existing files and reinstall tools")
    add("-l", "--list", action="store_true", help="show detected assistants and installable items")
    add("-V", "--version", action="version", version=f"%(prog)s {VERSION} (Scepsis {framework})")
    return p


def _choose(parser, flag: str, given: list[str] | None, available: list[str]) -> list[str]:
    if given is None:
        return list(available)
    unknown = [g for g in given if g not in available]
    if unknown:
        parser.error(f"{flag}: unknown {', '.join(unknown)} (available: {', '.join(available) or 'none'})")
    return [a for a in available if a in given]


def _home(path: Path) -> str:
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def _err(message: str) -> None:
    print(message, file=sys.stderr)


def _list(skills: list[Item], agents: list[Item], tools: list[str]) -> None:
    detected = detect_assistants()
    dirs = config_dirs()
    print("Assistants:")
    for a in ASSISTANTS:
        state = "detected" if a in detected else "not found"
        print(f"  {a:<9} {state:<10} {_home(dirs[a])}")
    print("Tools:  " + (", ".join(tools) or "none"))
    print("Skills: " + (", ".join(f"{i.name} {i.version}" for i in skills) or "none"))
    print("Agents: " + (", ".join(f"{i.name} {i.version}" for i in agents) or "none"))


def _install_tools(repo: Path, names: list[str], force: bool, dry_run: bool) -> tuple[int, list[str]]:
    """Install tools with `uv tool install`: (number of errors, tools installed)."""
    errors, installed = 0, []
    uv = shutil.which("uv")
    for name in names:
        if shutil.which(name) and not force:
            print(f"  {LABELS['skip-path']:<16} tool {name}")
            continue
        print(f"  {'install':<16} tool {name}")
        if not uv:
            _err(f"error: tool {name}: 'uv' is not on PATH; install it "
                 "(https://docs.astral.sh/uv/) and run again with -o tools")
            errors += 1
            continue
        if dry_run:
            installed.append(name)
            continue
        cmd = [uv, "tool", "install"] + (["--force", "--reinstall"] if force else [])
        result = subprocess.run(cmd + [str(repo / "tools" / name)])
        if result.returncode != 0:
            _err(f"error: tool {name}: 'uv tool install' failed (exit {result.returncode})")
            errors += 1
        else:
            installed.append(name)
    return errors, installed


def _install_items(
    items: list[Item],
    assistants: list[str],
    where: dict[str, Targets],
    shared_dirs: list[Path],
    manifest: Manifest,
    force: bool,
    dry_run: bool,
    installed_tools: list[str],
) -> None:
    """Render each item for each assistant and write it where it is safe to."""
    written: set[Path] = set()  # skill folders written in this run
    warned: set[tuple[str, str]] = set()
    for assistant in assistants:
        for item in items:
            if item.kind == "skills":
                folder = where[assistant].skills / item.name
                dest = folder / "SKILL.md"
                content = render_skill(assistant, item)
                # OpenCode also reads the shared dirs: a second copy would clash.
                if assistant == "opencode" and any(
                    d / item.name in written or (d / item.name).exists() for d in shared_dirs
                ):
                    print(f"  {LABELS['skip-shared']:<16} {item.label} {item.version} [{assistant}] → {_home(folder)}")
                    continue
            else:
                dest = where[assistant].agents / agent_filename(assistant, item.name)
                content = render_agent(assistant, item)
            action = manifest.decide(dest, content, force)
            print(f"  {LABELS[action]:<16} {item.label} {item.version} [{assistant}] → {_home(dest)}")
            if action not in WRITES and action != "unchanged":
                continue
            if action in WRITES:
                written.add(dest.parent)
            if not dry_run:
                if action in WRITES:
                    write_file(dest, content)
                manifest.record(dest, content, item.label, item.version)
            for command in item.meta.get("requires", []):
                missing = command not in installed_tools and not shutil.which(command)
                if missing and (item.label, command) not in warned:
                    warned.add((item.label, command))
                    _err(f"warning: {item.label} requires '{command}', which is not on PATH")


def main(argv: list[str] | None = None, repo: Path = REPO) -> int:
    parser = _parser(framework_version(repo) or "unknown")
    args = parser.parse_args(argv)

    skills, skill_errors = load_items(repo, "skills")
    agents, agent_errors = load_items(repo, "agents")
    tools = list_tools(repo)
    if args.list:
        _list(skills, agents, tools)
        return 0

    components = _choose(parser, "--only", _split(args.only), list(COMPONENTS))
    assistants_given = _split(args.assistant)
    assistants = _choose(parser, "--assistant", assistants_given, list(ASSISTANTS))
    if assistants_given is None:
        assistants = detect_assistants()
    skill_names = _choose(parser, "--skills", _split(args.skills),
                          sorted([i.name for i in skills] + list(skill_errors)))
    agent_names = _choose(parser, "--agents", _split(args.agents),
                          sorted([i.name for i in agents] + list(agent_errors)))
    tool_names = _choose(parser, "--tools", _split(args.tools), tools)
    overrides = {}
    for value in args.config_dir:
        assistant, sep, path = value.partition("=")
        if not sep or assistant not in ASSISTANTS or not path:
            parser.error(f"--config-dir: expected ASSISTANT=DIR with ASSISTANT one of {', '.join(ASSISTANTS)}")
        overrides[assistant] = Path(path).expanduser().absolute()
    scope = "project" if args.project_dir else (args.scope or "user")
    project_dir = (args.project_dir or Path.cwd()).expanduser().absolute()

    errors = 0
    for kind, problems, names in (("skill", skill_errors, skill_names), ("agent", agent_errors, agent_names)):
        if kind + "s" not in components:
            continue
        for name, problem in problems.items():
            if name in names:
                _err(f"error: {kind} {name}: {problem}")
                errors += 1
    if args.dry_run:
        print("Dry run: nothing will be written.")

    installed_now: list[str] = []
    if "tools" in components:
        tool_errors, installed_now = _install_tools(repo, tool_names, args.force, args.dry_run)
        errors += tool_errors

    wanted: list[Item] = []
    if "skills" in components:
        wanted += [i for i in skills if i.name in skill_names]
    if "agents" in components:
        wanted += [i for i in agents if i.name in agent_names]
    if wanted and not assistants:
        _err("note: no AI assistant detected, so no skills or agents were installed; "
             f"choose some with -a {','.join(ASSISTANTS)}")
        wanted = []

    manifest = Manifest(Path.home() / ".scepsis" / "installed.json")
    _install_items(
        wanted,
        assistants,
        targets(scope, project_dir, overrides),
        opencode_shared_skill_dirs(scope, project_dir),
        manifest,
        args.force,
        args.dry_run,
        installed_now,
    )
    if wanted and not args.dry_run:
        manifest.save()

    if not args.dry_run:
        for name in installed_now:
            if not shutil.which(name):
                _err(f"warning: '{name}' was installed but is not on PATH; run 'uv tool update-shell'")
    return 1 if errors else 0


if __name__ == "__main__":
    # Keep actions and warnings in order when stdout is a pipe.
    sys.stdout.reconfigure(line_buffering=True)
    sys.exit(main())
