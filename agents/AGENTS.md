# Scepsis - agents/AGENTS.md

## Description

- Read the local `README.md` for more information.

## Rules and conventions

- Each agent is placed within a folder with the agent name.
- Each agent is defined in a file called `AGENT.md` **without frontmatter** within its folder.
- Each agent has a generalized frontmatter in JSON format in a file called `frontmatter.json` within its folder.
- Agents are installed outside this repository, so an agent must be self-contained: it must not reference repository paths (`docs/`, `tools/`, …), nor assume direct access to the tools' data folders (e.g. `~/.scepsis/`). It works through the tools' CLIs and points to their built-in `--help` for details.
- Agents are agent-agnostic: the same definition is installed into any supported AI assistant (Claude Code, OpenAI Codex, DeepSeek-based tools, OpenCode, …). Options that differ per assistant or provider, such as the model, live in the frontmatter, keyed by provider.
- When an agent is installed, the installer (`installer/install.py`) combines the frontmatter and the markdown, adapting the former to the target AI assistant format (see `docs/usage/installation.md`). A new frontmatter field must be handled there too (validation in `_check_meta`, rendering in `render_agent`).

# Generalized frontmatter schema

```json
{
  "name": "verification",
  "description": "What the agent does and when to delegate to it.",
  "model": {
    "default": "anthropic",
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-6.1-sol",
    "deepseek": "deepseek-v4-pro"
  },
  "tools": ["read", "search", "shell"],
  "requires": ["chreos"]
}
```

| **Field** | **Type** | **Required** | **Notes** |
| --- | --- | --- | --- |
| `name` | string | yes | Equals the agent's folder name. Pattern `^[a-z0-9]+(-[a-z0-9]+)*$`, at most 64 characters. |
| `description` | string | yes | A single paragraph: what the agent does and when to delegate to it. Assistants use it to decide, so it must be enough on its own. |
| `model` | object | no | Model per provider: `anthropic`, `openai`, `deepseek` (more may be added), each a model ID as the provider's API names it. `default` names the provider to use when the target assistant can use several (e.g. OpenCode) and only one can be chosen. Without `model`, or without an entry for the target's provider, the assistant's default model is used. |
| `tools` | list of strings | no | Generic capabilities the agent may use: `read` (read files), `search` (find files and text in them), `shell` (run commands), `edit` (create and change files), `web` (fetch and search the web). Without `tools`, the assistant's defaults apply. |
| `requires` | list of strings | no | External commands the agent runs, which must be on `PATH`. Default: `[]`. |

## Mapping to assistants

How `installer/install.py` maps the fields:

| **Field** | **Claude Code** | **OpenCode** | **Codex** |
| --- | --- | --- | --- |
| `model` | The `anthropic` ID | `<provider>/<id>` from the `default` provider, e.g. `anthropic/claude-sonnet-5-5` | The `openai` ID |
| `tools` | `read` → `Read`; `search` → `Grep`, `Glob`; `shell` → `Bash`; `edit` → `Edit`, `Write`; `web` → `WebFetch`, `WebSearch` | Capabilities not listed are denied in `permission` (`read` → `read`; `search` → `grep`, `glob`, `list`; `shell` → `bash`; `edit` → `edit`; `web` → `webfetch`, `websearch`) | `sandbox_mode`: `workspace-write` with `edit`, else `read-only` |

Model IDs were checked against each provider's documentation on 2026-10-05; review them when providers release new models.
