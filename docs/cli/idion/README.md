# idion — Command Reference

Reference documentation for `idion`, the Scepsis user context CLI (`tools/idion/`): every command and option, the conventions they share, the context tree and file format, and the JSON output contract. It describes the implemented behaviour; the reasoning behind it is in the system design (`docs/system-designs/idion-data-model.md`). Installation and development instructions are in `tools/idion/README.md`.

## Contents

| **File** | **Contents** |
| --- | --- |
| `README.md` | This index, the root command and the conventions shared by all commands |
| `files.md` | The context tree, context files, folder descriptions (`_index.md`) and the file format |
| `commands.md` | `idion init`, `create`, `show`, `list`, `search`, `update`, `append`, `replace`, `edit`, `move`, `delete` |
| `folders.md` | `idion folder describe`, `idion folder show` |
| `check.md` | `idion check` |
| `json-output.md` | The JSON shapes printed by `--json`: a stable contract for scripts and agents |

## `idion`

```
idion [-h|--help] [-V|--version] COMMAND [ARGS]...
```

`-V`/`--version` prints `idion <version>`. `-h`/`--help` works on every command and group. Running `idion` or `idion folder` without a subcommand prints its help and exits with `2`.

Commands: `init`, `create`, `show`, `list`, `search`, `update`, `append`, `replace`, `edit`, `move`, `delete` (see `commands.md`), `folder` (see `folders.md`), `check` (see `check.md`).

## Conventions

**Identifiers.** A context file is named by its path relative to the context root, without `.md`: `user`, `teams/my-team`. A folder is named the same way with a trailing `/`: `teams/`, `company/projects/`. The root is `/`. Each segment is lowercase letters and digits separated by single hyphens, at most 64 characters, and an identifier has at most 8 segments. Identifiers are validated, never rewritten: absolute paths, `.` and `..`, empty segments, a trailing `.md`, names starting with `_` (reserved) and invalid segments are rejected. A command that expects a file and gets a folder, or the other way round, fails with a hint (`did you mean 'teams/'?`).

**Symbolic links.** No path through a symbolic link below the context root is accepted. The root itself may be a symbolic link.

**Text input.** Options that take text accept `-` to read it from standard input (`-b -`, `-t -`); heredocs and pipes work, and one trailing newline is dropped. Without piped input, the command fails instead of waiting on the terminal.

**Confirmations and `-f/--force`.** `delete` asks before deleting. `-f` answers yes. Without a terminal and without `-f`, it fails instead of waiting for an answer (`confirmation required: run in a terminal or pass -f`), which keeps agents and scripts from hanging. Declining exits with `1` (`cancelled`).

**Output.** Results go to standard output; warnings (`warning: …`) and errors (`Error: …`) go to standard error. Commands that write print the path of the file they wrote. `show`, `list`, `search`, `folder show` and `check` accept `--json`; the shapes are documented in `json-output.md`.

**Exit codes.** `0` success; `1` user or validation error (not found, invalid value, refused or unconfirmed operation, `check` found errors); `2` usage error (unknown command or option, missing argument or required option).

**Write lock.** Every command that writes holds an exclusive lock on `<root>/.idion.lock`. A second writer waits up to 10 seconds, then fails with exit `1`. Read-only commands don't lock.

**Context tree required.** Every command except `init` needs the context tree and fails with `run 'idion init' first` when it is missing.

**No timestamps.** idion keeps no `created` or `updated` fields; a change is visible in the file itself (and its modification time).
