# Scepsis - chreos

`chreos`, the Python based task manager CLI of the Scepsis framework. It manages projects, tasks and decisions locally.

## Why chreos?

*Chreos* (χρέος) is Greek for debt or duty: what one owes. Tasks, projects and decisions are exactly that, the work still owed.

Supported platforms: Linux and macOS (the workspace lock uses POSIX file locks).

## Getting started

```sh
chreos init --workspace-path ~/scepsis-workspace --source-git-path ~/code
chreos config show
chreos config set output.format json
```

`init` writes `~/.scepsis/config.toml` (commented, hand-editable) and creates the workspace with its default project. Every command, option and output format is documented in the reference: `docs/cli/chreos/`.

A task's life:

```sh
chreos project create website -t "Website"
chreos task create homepage -P website --source-type git --source-path site   # ~/code/site
cd "$(chreos task open website/homepage --assignee claude)"                    # git worktree on branch 'homepage'
chreos task ac append website/homepage -a "Renders at 320px" -a "Reviewed by a human"
chreos task notes append website/homepage -N "Hero implemented"
chreos task close website/homepage --status done                              # worktree removed, branch kept
chreos task list --all-projects --ready
```

## Build instructions

Requires [uv](https://docs.astral.sh/uv/). From `tools/chreos/`:

```sh
uv build          # wheel and sdist into dist/
```

## Test instructions

From `tools/chreos/`:

```sh
uv sync           # create .venv with the pinned dependencies
uv run pytest
```

## Installation instructions

Install the `chreos` command for the current user (from the repository root):

```sh
./installer/install.sh -o tools -t chreos    # or: uv tool install ./tools/chreos
chreos --version
```

The installer skips `chreos` when it is already on `PATH`; add `-f` to upgrade it from this checkout. See `docs/usage/installation.md`.

For development, `uv run chreos` runs it from the source tree without installing.

## Versions and dependencies

| **Component** | **Version** |
| --- | --- |
| Python | `3.14.8` |
| uv (build backend `uv_build`) | `0.11.15` |
| Click | `8.5.0` |
| ruamel.yaml | `0.19.1` |
| tomlkit | `0.15.1` |
| pytest (dev) | `9.1.1` |
| git (runtime) | `>= 2.30` |
