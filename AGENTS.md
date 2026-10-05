# Scepsis - AGENTS.md

## Description

- Read `README.md` for a general project description.
- Under `docs/` there is additional documentation about the project. In the 10 first lines of each file there is an abstract including the document scope and contents. Read the full file only as needed.
- Some directories have additional `AGENTS.md` files with additional context for their scope.

## Structure

| **Target** | **Description** |
| --- | --- |
| `AGENTS.md` | AI agent context (this file) |
| `README.md` | General project description |
| `docs/` | Project documentation |
| `skills/` | Default skill definitions for installing in the framework |
| `agents/` | Default agent definitions for installing in the framework |
| `tools/` | Default tool definitions available in the framework |
| `templates/` | Template definitions for the markdown files used in the framework |
| `VERSION` | The Scepsis framework version |
| `CHANGELOG.md` | Changes per framework release and component |
| `installer/` | Installer of tools, skills and agents for each AI assistant (`install.sh` → `install.py`) |

## Rules and conventions

- Every file except for `AGENTS.md` is meant to be read by humans and agents alike.
- Always attempt one task at a time.
- Always plan before attempting a task. Use plan mode for this if available.
- Always ask the user for approval before executing the plan.
- Always update any necessary documentation file after doing any change.
- The README should stay brief and focused, as it serves as the project frontpage. Any deeper documentation goes into `docs/`.

## Versioning

- Every component has a semantic version (`MAJOR.MINOR.PATCH`): the framework (`VERSION`), each tool (`tools/<name>/pyproject.toml`), the installer (`installer/pyproject.toml` and `VERSION` in `installer/install.py`), and each skill and agent (`version` in its `frontmatter.json`). Templates, documentation and conventions belong to the framework.
- Before 1.0.0, a minor bump adds features or breaks compatibility, and a patch bump fixes things. From 1.0.0, standard semver applies.
- A change to a component bumps its version in the same commit and adds an entry to `CHANGELOG.md` under `## [Unreleased]`, in a `### <component> <version>` section (`### chreos 0.4.0`, `### skill task 0.2.0`, `### installer 0.2.0`, or `### Framework` for the shared parts), with `#### Added`/`Changed`/`Fixed`/`Removed` lists.
- A release bumps `VERSION` and renames `## [Unreleased]` to `## Scepsis <version> — <YYYY-MM-DD>`, leaving a new empty `## [Unreleased]` above it.
- No git tags before 1.0.0. From 1.0.0, each framework release is tagged `v<version>`.
- `installer/tests/test_repository.py` fails when a current version has no `CHANGELOG.md` entry.
