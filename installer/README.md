# Scepsis - installer

Installs the Scepsis tools, skills and agents for the AI assistants found on the machine (Claude Code, OpenAI Codex, OpenCode), without modifying files that already exist.

Usage, options and the per-assistant formats are described in the user guide: [`docs/usage/installation.md`](../docs/usage/installation.md).

```sh
./installer/install.sh        # everything, for every assistant detected
./installer/install.sh -h     # options
```

## Structure

| **File** | **Purpose** |
| --- | --- |
| `install.sh` | POSIX `sh` wrapper: runs `install.py` with `uv`, or with `python3` ≥ 3.10 when `uv` is missing |
| `install.py` | The installer. Standard library only and no POSIX-only calls, so another wrapper (e.g. PowerShell) can reuse it |
| `tests/` | pytest suite |
| `AGENTS.md` | Context for AI agents working on the installer |

Supported platforms: Linux and macOS. The wrapper uses POSIX `sh` only, so it should work on macOS, but it has only been tested on Linux.

## Test instructions

From `installer/`:

```sh
uv sync           # create .venv with the pinned dev dependencies
uv run pytest
```

## Versions and dependencies

| **Component** | **Version** |
| --- | --- |
| Python | `>= 3.10` (development: `3.14.8`) |
| uv (to install the tools) | `0.11.15` |
| pytest (dev) | `9.1.1` |
