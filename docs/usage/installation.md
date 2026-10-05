# Installing Scepsis

User guide for `installer/install.sh`: what it installs, where, and for which AI assistant; how it avoids modifying existing files; every option, with examples; and how skill and agent definitions are translated into each assistant's format.

Scope: Linux and macOS (macOS is supported by design but untested). Requirements: `uv` (https://docs.astral.sh/uv/) to install the tools; skills and agents only need Python ≥ 3.10.

For development of the installer itself, see `installer/README.md`.

## Quick start

From the repository root:

```sh
./installer/install.sh -l     # what it finds: assistants, tools, skills, agents
./installer/install.sh -n     # dry run: what it would do
./installer/install.sh        # install everything for every assistant detected
```

## What gets installed

| **Component** | **Source** | **How** |
| --- | --- | --- |
| Tools | `tools/<name>/` (`chreos`, `idion`) | `uv tool install`; skipped when the command is already on `PATH` |
| Skills | `skills/<name>/` | `SKILL.md` + `frontmatter.json`, rendered into each assistant's skill format |
| Agents | `agents/<name>/` | `AGENT.md` + `frontmatter.json`, rendered into each assistant's agent format |

Templates need no installation: `chreos` includes them.

## Assistants and destinations

An assistant counts as detected when its command is on `PATH` or its config dir exists. Without `-a`, the installer targets every assistant it detects.

| **Assistant** | **Detected by** | **Skills** | **Agents** |
| --- | --- | --- | --- |
| `claude` (Claude Code) | `claude`, `${CLAUDE_CONFIG_DIR:-~/.claude}` | `<config>/skills/<name>/SKILL.md` | `<config>/agents/<name>.md` |
| `codex` (OpenAI Codex) | `codex`, `${CODEX_HOME:-~/.codex}` | `~/.agents/skills/<name>/SKILL.md` | `<config>/agents/<name>.toml` |
| `opencode` (OpenCode) | `opencode`, `${XDG_CONFIG_HOME:-~/.config}/opencode` | `<config>/skills/<name>/SKILL.md` | `<config>/agents/<name>.md` |

With `-p DIR` (project scope), the same layout goes under `DIR/.claude/`, `DIR/.agents/skills/` and `DIR/.codex/agents/`, and `DIR/.opencode/`.

OpenCode also reads skills from `.claude/skills/` and `.agents/skills/`. When a skill with the same name is already in one of those, or is installed there in the same run, it is not copied into OpenCode's own dir (shown as `skip (shared)`), so OpenCode never sees two skills with the same name.

## Existing files are never modified

Every file the installer writes is recorded in `~/.scepsis/installed.json`, with a hash of its content and the item and version it came from. For each destination file:

| **Situation** | **Action** |
| --- | --- |
| It doesn't exist | `install` |
| It already has the right content | `unchanged` |
| The installer wrote it and nobody has changed it since | `update` (how upgrades work) |
| It belongs to the user, or the user edited it after installation | `skip (exists)` / `skip (modified)` |

`-f` overwrites in the last case (`overwrite`). Writes are atomic, and nothing is ever deleted.

## Options

Each list option takes comma-separated values and can be repeated (`-a claude -a codex` is the same as `-a claude,codex`).

| **Option** | **Meaning** |
| --- | --- |
| `-a, --assistant LIST` | Assistants to install for: `claude`, `codex`, `opencode`. Default: those detected |
| `-o, --only LIST` | Components: `tools`, `skills`, `agents`. Default: all |
| `-s, --skills LIST` | Only these skills |
| `-g, --agents LIST` | Only these agents |
| `-t, --tools LIST` | Only these tools |
| `-S, --scope user\|project` | `user` (default): the assistants' user config dirs. `project`: a project's dirs |
| `-p, --project-dir DIR` | Project to install into; implies `-S project`. Default with `-S project`: the current dir |
| `-c, --config-dir ASSISTANT=DIR` | Use `DIR` as that assistant's config dir (repeatable). For `codex` this moves agents only: Codex reads user skills from `~/.agents/skills` |
| `-n, --dry-run` | Show what would be done; write nothing |
| `-f, --force` | Overwrite existing files and reinstall tools already on `PATH` |
| `-l, --list` | Show detected assistants and installable items (with their versions), then exit |
| `-V, --version` | Show the installer and Scepsis framework versions |
| `-h, --help` | Show the options |

Each output line shows the action, the item and its version, the assistant and the destination, e.g. `install  skill task 0.1.0 [claude] → ~/.claude/skills/task/SKILL.md`. Versions are not written into the assistants' files.

Exit status: `0` on success, `1` when something failed (a tool install, an invalid definition), `2` on a usage error. Each failure is reported and the rest still installs.

## Examples

```sh
./installer/install.sh -o tools                        # only chreos and idion
./installer/install.sh -o tools -t chreos -f           # upgrade chreos from this checkout
./installer/install.sh -a claude -o skills -s task     # only the task skill, only for Claude Code
./installer/install.sh -a codex,opencode -o agents     # agents for Codex and OpenCode
./installer/install.sh -p ~/code/website -o skills,agents   # into a project, not the user dirs
./installer/install.sh -c claude=~/.claude-work        # a second Claude Code config dir
```

## How definitions are translated

Skills and agents are written once, in a generalized format (`skills/AGENTS.md`, `agents/AGENTS.md`), and rendered per assistant:

| **Field** | **Claude Code** | **Codex** | **OpenCode** |
| --- | --- | --- | --- |
| Skill `name`, `description` | YAML frontmatter | YAML frontmatter | YAML frontmatter |
| Skill `user_invocable: false` | `user-invocable: false` | No equivalent; ignored | No equivalent; ignored |
| Agent file | `<name>.md`, YAML frontmatter + body | `<name>.toml`, body as `developer_instructions` | `<name>.md`, `mode: subagent` |
| Agent `model` | The `anthropic` entry | The `openai` entry | `<default>/<id>` from the `default` provider |
| Agent `tools` | `read`→Read, `search`→Grep, Glob, `shell`→Bash, `edit`→Edit, Write, `web`→WebFetch, WebSearch | `sandbox_mode`: `workspace-write` with `edit`, else `read-only` | `permission: deny` for each capability not listed |
| `requires` | Warning if the command is not on `PATH` | Same | Same |

Without a `model` entry for the assistant's provider, the assistant's default model is used. Without `tools`, the assistant's default permissions apply.
