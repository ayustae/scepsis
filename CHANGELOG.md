# Changelog

All notable changes to Scepsis. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and every component follows [Semantic Versioning](https://semver.org/).

Each release of the framework (`VERSION`) lists the components that changed, under a `### <component> <version>` heading: the tools (`chreos`, `idion`), the `installer`, each `skill <name>` and `agent <name>`, and `Framework` for the shared parts (templates, documentation, conventions). Changes not yet released go under `[Unreleased]`.

## [Unreleased]

## Scepsis 0.1.0 — 2026-10-05

First release.

### Framework

#### Added

- Repository layout and conventions (`AGENTS.md` files), `README.md` and the MIT license.
- Markdown templates for projects, tasks and decisions (`templates/`).
- Documentation index (`docs/`): system designs for chreos and idion, their CLI references, and the installation guide.
- Generalized frontmatter schemas for skills and agents, adapted to each AI assistant on installation.
- Versioning: the framework version in `VERSION`, a version per component, and this changelog.

### installer 0.1.0

#### Added

- `installer/install.sh`: installs the tools, skills and agents for the AI assistants found (Claude Code, Codex, OpenCode), with options to choose what, where and for which assistant.
- Never modifies existing files: only files it wrote, unchanged since, are updated (`~/.scepsis/installed.json`).

### skill task 0.1.0

#### Added

- Defines, breaks down, routes and tracks tasks and decisions through `chreos`.

### skill context 0.1.0

#### Added

- Keeps durable context about the user and their work through `idion`.

### agent verification 0.1.0

#### Added

- Checks, against the real state, that a finished task is done and is what was asked, before it is closed.

### chreos 0.3.0

#### Added

- `chreos task ac check|uncheck` to tick and untick acceptance criteria.

### chreos 0.2.0

#### Added

- `chreos decision description` to show and write a decision's body.

### chreos 0.1.0

#### Added

- `chreos`, the task, project and decision manager CLI: `init`, `config`, `project`, `task` (including the open/close lifecycle on git worktrees), `decision` and `check`, with JSON output.

### idion 0.3.0

#### Added

- `idion search` to find text in context files.

### idion 0.2.0

#### Added

- `idion replace` to rewrite a context file's body.

### idion 0.1.0

#### Added

- `idion`, the user context manager CLI: `init`, `create`, `show`, `list`, `update`, `append`, `edit`, `move`, `delete`, `folder` and `check`, with JSON output.
