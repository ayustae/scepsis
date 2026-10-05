# Scepsis - installer/AGENTS.md

## Description

- Read the local `README.md` for more information.
- User guide (keep it in sync with every option or format change): `docs/usage/installation.md`.

## Structure

- `install.sh`: POSIX `sh` wrapper only (no bashisms); it finds `uv` or `python3` and passes all arguments through. Logic goes in `install.py`.
- `install.py`, by section:
  - Definitions: `load_items` (with `_check_meta` validation) and `list_tools` read `skills/`, `agents/` and `tools/`.
  - Assistants: `config_dirs` (the only place with OS-specific paths), `detect_assistants`, `targets` (where skills/agents go per scope), `opencode_shared_skill_dirs`.
  - Rendering: `render_skill`, `render_agent`, `agent_filename`. YAML values are written with `_yaml_str` (JSON strings), TOML with `_toml_str`/`_toml_text`; never interpolate raw text.
  - Writing: `write_file` (atomic) and `Manifest` (`~/.scepsis/installed.json`).
  - CLI: `main`, `_install_tools`, `_install_items`.

## Rules and conventions

- Standard library only, Python >= 3.10 (no `tomllib`, no 3.11+ syntax), and no POSIX-only calls, so a future Windows wrapper can reuse `install.py`.
- Never delete files, and never write a destination without `Manifest.decide`: files the installer did not write, or that the user edited, are left alone unless `--force` is given.
- A new frontmatter field in `skills/` or `agents/` must be handled here (`_check_meta`, then `render_skill`/`render_agent`), and the format tables in `docs/usage/installation.md` and `agents/AGENTS.md` updated.
- A new assistant needs `ASSISTANTS`, `config_dirs`, `targets`, the rendering functions, tests and the user guide.
- Use a Test Driven Development (TDD) approach, as in `tools/AGENTS.md`: failing test first, minimum implementation, then refactor.
- Tests: `tests/conftest.py` provides `repo` (a fake repository built with `RepoBuilder`) and `home` (isolated `HOME`, assistant env vars removed, `PATH` holding only `home.bin`). Fake commands (`fake_command`, `fake_uv`) can only use shell built-ins or absolute paths, since nothing else is on `PATH`. CLI tests call `install.main([...], repo=...)` and check files with `tree()`.

## Key commands

Run from `installer/`:

- `uv sync`: install the pinned dev dependencies into `.venv`.
- `uv run pytest`: run the test suite.
- `uvx pyflakes install.py tests/`: catch unused imports and names.
- `./install.sh -n`: dry run against the real home (writes nothing).
