# chreos — Configuration

Reference for the chreos configuration: the keys of `~/.scepsis/config.toml`, the path rule, template overrides, and the `chreos init` and `chreos config` commands. Conventions shared by all commands are in `README.md`.

## `~/.scepsis/config.toml`

```toml
[workspace]
path = "~/scepsis-workspace"

[defaults]
project = "default"

[source]
git_path = "~/code"       # optional
local_path = "~/files"    # optional

[output]
format = "text"           # optional
```

| **Key** | **Type** | **Required** | **Meaning** |
| --- | --- | --- | --- |
| `workspace.path` | path | yes | Workspace root; project folders live directly under it. |
| `defaults.project` | name | yes | Project used when a command gets no `-P`. Must exist. |
| `source.git_path` | path | no | Base folder for relative `git` task sources. |
| `source.local_path` | path | no | Base folder for relative `local` task sources. |
| `output.format` | `text` or `json` | no | Default output of read commands; `text` if absent. |

**Path rule.** Paths in the config and in options are absolute or start with `~` / `~/` (expanded to the home folder; `~user` is not accepted). The only relative paths accepted anywhere are task source paths, resolved against the base folder of their type. Paths are stored as written.

The file is shared by the whole Scepsis framework: chreos reads and writes only the keys above and preserves everything else, including comments.

**Template overrides.** A file named `PROJECT.md`, `TASK.md` or `DECISION.md` in `~/.scepsis/templates/` replaces the packaged template of that item type. It must keep every frontmatter key of the original; placeholders (`<name>`, `<title>`, `<summary>`, `<project>`, `<timestamp>`) are filled in at creation.

## `chreos init`

```
chreos init [--workspace-path PATH] [--default-project NAME]
            [--source-git-path PATH] [--source-local-path PATH] [-f]
```

Writes a commented `~/.scepsis/config.toml`, creates the workspace folder and the default project (with its `tasks/`, `.archive/` and `decisions/` folders) if it doesn't exist.

- `--workspace-path PATH`: prompted when omitted on a terminal; required otherwise (usage error).
- `--default-project NAME`: default `default`.
- `--source-git-path PATH`, `--source-local-path PATH`: base folders for relative sources. They are not created; a missing one is a warning.
- `-f`, `--force`: overwrite an existing config without asking. Overwriting writes a fresh file from the given options (unspecified optional keys are dropped). Existing projects are never touched, so re-running `init` is safe.

## `chreos config show`

```
chreos config show [--json]
```

Prints `key = value` for each configured key, in the order of the table above. `--json` prints them as a nested object (`{"workspace": {"path": …}, …}`).

## `chreos config get`

```
chreos config get KEY [--json]
```

Prints one value (`KEY` is dotted, e.g. `source.git_path`). An unset optional key prints nothing; with `--json` it prints `null`. Only the keys of the table above are accepted.

## `chreos config set`

```
chreos config set KEY VALUE
```

Changes one key, validated: paths follow the path rule, `workspace.path` must be an existing folder, `defaults.project` must name an existing project, `output.format` is `text` or `json`. `none` removes an optional key; required keys can't be removed. Comments and key order are preserved.
