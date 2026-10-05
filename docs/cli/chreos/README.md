# chreos — Command Reference

Reference documentation for `chreos`, the Scepsis task manager CLI (`tools/chreos/`): every command and option, the conventions they share, the configuration, the on-disk file formats and the JSON output contract. It describes the implemented behaviour; the reasoning behind it is in the system design (`docs/system-designs/chreos-data-model.md`). Installation and development instructions are in `tools/chreos/README.md`.

## Contents

| **File** | **Contents** |
| --- | --- |
| `README.md` | This index, the root command and the conventions shared by all commands |
| `configuration.md` | `~/.scepsis/config.toml`, `chreos init`, `chreos config` |
| `files.md` | Workspace layout and the formats of `PROJECT.md`, `TASK.md` and decision files |
| `projects.md` | `chreos project` |
| `tasks.md` | `chreos task`: items, lifecycle, workspace operations and sections |
| `decisions.md` | `chreos decision` |
| `check.md` | `chreos check` |
| `json-output.md` | The JSON shapes printed by `--json`: a stable contract for scripts and agents |

## `chreos`

```
chreos [-h|--help] [-V|--version] COMMAND [ARGS]...
```

`-V`/`--version` prints `chreos <version>`. `-h`/`--help` works on every command and group. Running `chreos` or a group without a subcommand prints its help and exits with `2`.

Command groups: `init`, `config` (see `configuration.md`), `project`, `task`, `decision`, `check`.

## Conventions

**Item names.** Projects, tasks and decisions have names made of lowercase letters and digits in segments separated by single hyphens (`redesign-homepage`), at most 64 characters. Names are validated, never rewritten.

**NAME arguments.** Task and decision commands take `NAME` (in the project given with `-P PROJECT`, or the configured default project) or the qualified form `PROJECT/NAME`. A qualified name that contradicts `-P` is an error.

**Item references.** Dependencies and `## References` entries name other items with a prefix: `task:NAME`, `task:PROJECT/NAME`, `decision:NAME`, `decision:PROJECT/NAME`. Without a project, a reference points into the project of the item holding it. A bare name is rejected with a hint (`did you mean 'task:x' or 'decision:x'?`).

**Labels.** `key` or `key=value`; keys use `[a-z0-9_-]`, values are non-empty without whitespace, commas or `=`. Labels are lowercased and deduplicated. Every `-l/--label` value may hold several comma-separated labels. On `update`, `--remove-label` is applied after `-l`.

**Clearing values.** Options that set an optional value accept `none` to clear it: `--summary none`, `--priority none`, `--due none`, `--assignee none`, and `config set KEY none`.

**Confirmations and `-f/--force`.** Some operations ask first: deleting, losing uncommitted work or extra files in a task folder, marking a task `done` with unchecked acceptance criteria or unsatisfied dependencies, marking a decision `decided` with unsatisfied dependencies, replacing a task's assignee, overwriting the config. `-f` answers yes to every confirmation of that command. Without a terminal and without `-f`, the command fails instead of waiting for an answer (useful for agents and scripts).

**Text input.** Commands taking `[TEXT]` read standard input when it is omitted (heredocs and pipes work); on a terminal without TEXT they fail with a hint.

**Output.** Results go to standard output; warnings (`warning: …`) and errors (`Error: …`) go to standard error. `list`, `show` and the other read commands accept `--json`; with `output.format = "json"` in the config, JSON is the default. The JSON shapes are documented in `json-output.md`.

**Exit codes.** `0` success; `1` user or validation error (not found, invalid value, refused or unconfirmed operation, `check` found errors); `2` usage error (unknown command or option, missing argument).

**Workspace lock.** Every command that writes holds an exclusive lock on `<workspace>/.scepsis.lock`. A second writer waits up to 10 seconds, then fails with exit `1`. Read-only commands don't lock.

**Timestamps.** Every change made through chreos bumps the item's `updated` field. Edits made with other tools don't.
