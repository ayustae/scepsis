# Scepsis - idion

`idion`, the Python based user context manager CLI of the Scepsis framework. It manages Markdown files that describe the user to AI models.

## Why idion?

*Idion* (ἴδιον) is Greek for "what is one's own": the user's own context, kept where AI models can find it.

Supported platforms: Linux and macOS.

Every command, option and output format is documented in the reference: `docs/cli/idion/`. The design and its reasoning are in `docs/system-designs/idion-data-model.md`.

## Getting started

```sh
idion init        # creates ~/.scepsis/context/ (readable only by you)
idion create user -d "The user: role, background, working preferences."
idion create teams/my-team -d "My team: members and rituals." -b - <<'EOF'
# My team
...
EOF
idion folder describe teams/ -d "My team and the other teams in the department."
idion list --depth 1          # what an AI loads first: '<id> — <description>' lines
idion search ingestion        # files mentioning it, with the matching lines
idion show teams/my-team
idion append user -t "Prefers concise answers."
idion replace user -b - <<'EOF'   # rewrite the whole body
# User
...
EOF
idion update user -d "The user: role, background, preferences and working hours."
idion check                   # validate the whole tree; exit 1 on errors
```

Every other command needs the context tree and asks you to run `idion init` when it's missing.

## Build instructions

Requires [uv](https://docs.astral.sh/uv/). From `tools/idion/`:

```sh
uv build          # wheel and sdist into dist/
```

## Test instructions

From `tools/idion/`:

```sh
uv sync           # create .venv with the pinned dependencies
uv run pytest
```

## Installation instructions

Install the `idion` command for the current user (from the repository root):

```sh
./installer/install.sh -o tools -t idion    # or: uv tool install ./tools/idion
idion --version
```

The installer skips `idion` when it is already on `PATH`; add `-f` to upgrade it from this checkout. See `docs/usage/installation.md`.

For development, `uv run idion` runs it from the source tree without installing.

## Versions and dependencies

| **Component** | **Version** |
| --- | --- |
| Python | `3.14.8` |
| uv (build backend `uv_build`) | `0.11.15` |
| Click | `8.5.0` |
| ruamel.yaml | `0.19.1` |
| pytest (dev) | `9.1.1` |
