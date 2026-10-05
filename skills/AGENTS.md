# Scepsis - skills/AGENTS.md

## Description

- Read the local `README.md` for more information.

## Rules and conventions

- Each skill is placed within a folder with the skill name.
- Each skill is defined in a file called `SKILL.md` **without frontmatter** within its folder.
- Each skill has a generalized frontmatter in JSON format in a file called `frontmatter.json` within its folder.
- Skills are installed outside this repository, so a skill must be self-contained: it must not reference repository paths (`docs/`, `tools/`, …), nor assume direct access to the tools' data folders (e.g. `~/.scepsis/`). It works through the tools' CLIs and points to their built-in `--help` for details.
- When a skill is installed, the installer (`installer/install.py`) combines the frontmatter and the markdown, adapting the former to the target AI assistant format (see `docs/usage/installation.md`). A new frontmatter field must be handled there too (validation in `_check_meta`, rendering in `render_skill`).

# Generalized frontmatter schema

```json
{
  "name": "task",
  "version": "0.1.0",
  "description": "What the skill does and when to use it, including the phrases that should trigger it.",
  "requires": ["chreos"],
  "user_invocable": true
}
```

| **Field** | **Type** | **Required** | **Notes** |
| --- | --- | --- | --- |
| `name` | string | yes | Equals the skill's folder name. Pattern `^[a-z0-9]+(-[a-z0-9]+)*$`, at most 64 characters. |
| `version` | string | yes | The skill's semantic version (`MAJOR.MINOR.PATCH`). Bump it with every change to the skill and add a `### skill <name> <version>` entry to `CHANGELOG.md`. |
| `description` | string | yes | A single paragraph: what the skill does and when to use it, with trigger phrases. Assistants use it to decide whether to load the skill, so it must be enough on its own. |
| `requires` | list of strings | no | External commands the skill runs, which must be on `PATH`. The installer can check them and map them to the target assistant's tool permissions. Default: `[]`. |
| `user_invocable` | boolean | no | Whether the user can invoke the skill directly as a command (e.g. `/task`). Default: `true`. |
