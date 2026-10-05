# chreos — `chreos task`

Reference for the `chreos task` commands: creating, changing, listing and reading tasks; the lifecycle (`open`, `close`); workspace operations (`archive`, `restore`, `rename`, `move`, `delete`); and the section commands (`description`, `ac`, `refs`, `notes`). Shared conventions (NAME forms, `-P`, references, `none`, `-f`, output, exit codes) are in `README.md`; the file format, phases and statuses are in `files.md`.

All commands taking NAME accept `-P`, `--project`. Archived tasks are read-only: only `show`, `path`, `list --archived`, `restore`, `delete`, `rename`, `move` and the section `show` commands work on them; other commands fail with a hint to restore the task.

## `chreos task create`

```
chreos task create NAME [-P|--project PROJECT] [-t TITLE] [-s SUMMARY] [-l LABEL]... [--source-type git|local --source-path PATH]
                   [--priority P] [--due DATE] [--assignee TEXT] [--dep REF]...
```

Creates `tasks/NAME/TASK.md` (phase `closed`, status `new`) and prints its path.

- `-t`, `--title` (default NAME), `-s`, `--summary`, `-l`, `--label` (repeatable, comma-separated accepted).
- `--source-type` and `--source-path`: given together. The path is absolute, `~`, or relative to `source.git_path`/`source.local_path`. A source that doesn't resolve yet is a warning (it is required only to open the task).
- `--priority`: `low`, `medium`, `high`, `critical`. `--due`: `YYYY-MM-DD`. `--assignee`: free single-line text.
- `--dep`, `--depends-on`: repeatable item reference; each must resolve and must not create a dependency cycle.

## `chreos task update`

```
chreos task update NAME [-P|--project PROJECT] [-t TITLE] [-s SUMMARY|none] [-l LABEL]... [--remove-label LABEL]... [--status S]
                   [--source-type T] [--source-path PATH] [--priority P|none] [--due DATE|none] [--assignee TEXT|none]
                   [--dep REF]... [--remove-dep REF]... [-f]
```

Changes the given fields with a single write; at least one option is required.

- `-t`, `--title`; `-s`, `--summary`; `-l`, `--label`; `--remove-label`.
- `--status`: must be allowed in the current phase (a closed task can become `done` or `cancelled`, not `todo`; use `open`/`close` to change the phase).
- `--source-type`, `--source-path`: closed tasks only. With an existing source, either may change alone.
- `--priority`, `--due`, `--assignee`: `none` clears. Replacing one assignee with another asks for confirmation; clearing doesn't.
- `--dep`, `--depends-on` adds; `--remove-dep` removes the dependency pointing at the same item (`task:x` also removes `task:PROJECT/x`); an unknown one is a warning.
- Becoming `done` with unchecked acceptance criteria or unsatisfied dependencies (after the changes) asks for confirmation.
- `-f`, `--force`: skip the confirmations.

## `chreos task list`

```
chreos task list [-P PROJECT | --all-projects] [filters] [--sort KEY] [--json]
```

Lists tasks as `name  phase  status  priority  due  title` rows (`project/name` with `--all-projects`). By default `done` and `cancelled` tasks are hidden.

- `-P`, `--project` (default: the default project) or `--all-projects`. `--archived`: list archived tasks instead of live ones.
- `-l`, `--label`, `-n`, `--name`, `-t`, `--title`, `-s`, `--summary`, `-S`, `--search`: as for `project list`.
- `--status` (repeatable, OR), `--all` (every status), `--phase` (`open`/`closed`, repeatable, OR).
- `--ready`: only tasks that can be worked on next (live, not done/cancelled, all dependencies satisfied).
- `--depends-on REF`: only tasks that depend on REF (resolved against `-P` or the default project).
- `--priority` (repeatable, OR), `--assignee` (repeatable, OR), `--unassigned`.
- `--due-before DATE`: due strictly before DATE. `--overdue`: due before today and not done or cancelled.
- `--sort`: `name` (default), `created`, `updated`, `status`, `priority` (critical first) or `due` (earliest first); unset values last; ties by project, then name.
- `--json`: see `json-output.md`.

## `chreos task show`

```
chreos task show NAME [-P|--project PROJECT] [--json]
```

Prints `TASK.md` (live or archived), then a `Dependencies:` block (each reference with its status and `satisfied`/`unsatisfied`) and a `Dependents:` block. `--json` includes them as `dependencies` and `dependents`.

## `chreos task path`

```
chreos task path NAME [-P|--project PROJECT] [--work]
```

Prints the absolute path of the task file. `--work` prints the `work/` folder instead (open tasks only).

## `chreos task edit`

```
chreos task edit NAME [-P|--project PROJECT]
```

Opens `TASK.md` in `$VISUAL`/`$EDITOR` and validates it afterwards, as `project edit`, also checking that the dependencies resolve and form no cycle and that the item references in `## References` resolve. Not for archived tasks.

## `chreos task open`

```
chreos task open NAME [-P|--project PROJECT] [--status S] [--assignee TEXT] [--recreate] [--base REF] [-f]
```

Makes the task workable and prints the path of its `work/` folder on standard output (the status goes to standard error), so `cd "$(chreos task open NAME)"` works.

On a closed task (including one closed as `done`/`cancelled`, i.e. reopening): the source is required and must resolve; files left in the folder are cleaned up first (with the safety prompt); then `work/` is created:

- **git source:** a worktree on the branch named after the task, reused if it exists, otherwise created from `--base REF` (default `origin/HEAD` if the repository has it, else `HEAD`). Fails if the branch is checked out in another worktree.
- **local source:** a symbolic link to the folder.

The phase becomes `open` and the status `--status` or, by default, `todo` when every dependency is satisfied, else `on-hold`.

On an open task: a missing `work/` is recreated; `--recreate` removes and recreates it (with the safety prompt, only `work/` is touched); `--status` is applied without recomputing.

- `--status`: `todo`, `on-hold`, `in-progress`, `done`, `cancelled` (`done` asks for confirmation as in `update`).
- `--assignee`: assign while opening, same rule as `update`.
- `-f`, `--force`: skip the confirmations.

## `chreos task close`

```
chreos task close NAME [-P|--project PROJECT] [--status done|cancelled] [-f]
```

On an open task: sets `--status` if given (`done` asks for confirmation), refuses unless the status is `done` or `cancelled`, then removes everything in the task folder except `TASK.md` and sets the phase to `closed`. A git worktree is removed but **its branch is kept**; a symbolic link is removed without touching its target.

**Safety prompt:** before removing anything, chreos asks for confirmation if something would be lost: uncommitted or untracked changes in the worktree, a `work/` that is neither a link nor a working worktree, or other files in the task folder. The prompt lists them.

On a closed task, `close` only re-runs the cleanup; `--status` is ignored with a warning. `-f`, `--force` skips the confirmations.

## `chreos task archive`

```
chreos task archive NAME [-P|--project PROJECT] [--status done|cancelled] [-f]
```

Moves a closed task's `TASK.md` to `.archive/NAME.md`, sets `archived`, and removes its folder. References to it keep resolving. On an open task it fails unless `-f`, `--force` is given, which closes it first (with `--status` if given, skipping its confirmations).

## `chreos task restore`

```
chreos task restore NAME [-P|--project PROJECT]
```

Moves an archived task back to `tasks/NAME/TASK.md` and removes `archived`. The task stays closed.

## `chreos task rename`

```
chreos task rename NAME NEW_NAME [-P|--project PROJECT]
```

Renames a closed or archived task: its folder or archived file, `name`, every reference to it, and its git branch if one exists in the source repository (refused if a branch named NEW_NAME exists; a source that doesn't resolve leaves the branch alone with a warning).

## `chreos task move`

```
chreos task move NAME PROJECT [-P|--project PROJECT]
```

Moves a closed or archived task to another project (the name must be free there) and updates `project`. References are rewritten in both directions so they keep pointing at the same items. The git branch is unchanged.

## `chreos task delete`

```
chreos task delete NAME [-P|--project PROJECT] [-f]
```

Deletes a live or archived task after a confirmation listing the items that will lose references to it; those references are removed. An open task is cleaned up first, with the safety prompt. `-f`, `--force` skips the confirmations.

## `chreos task description show`

```
chreos task description show NAME [-P|--project PROJECT]
```

Prints the content of `## Description`.

## `chreos task description append`

```
chreos task description append NAME [TEXT] [-P|--project PROJECT]
```

Adds TEXT (or standard input) after the existing content, separated by a blank line. No `# `/`## ` heading lines or unclosed code fences; `###` and deeper are fine. A missing section is recreated in its template position.

## `chreos task description replace`

```
chreos task description replace NAME [TEXT] [-P|--project PROJECT]
```

Replaces the content with TEXT (or standard input); empty text clears it.

## `chreos task ac show`

```
chreos task ac show NAME [-P|--project PROJECT] [--json]
```

Prints the acceptance criteria as `- [ ] …` / `- [x] …` lines; `--json` as `{text, checked}` objects.

## `chreos task ac append`

```
chreos task ac append NAME (-a TEXT)... [-P|--project PROJECT]
```

Adds unchecked criteria after the last one. `-a`, `--ac`, `--acceptance-criteria`: repeatable, at least one, single line each. Ticking criteria is done by hand in the file.

## `chreos task ac replace`

```
chreos task ac replace NAME (-a TEXT)... [-P|--project PROJECT]
```

Replaces all criteria with the given ones, all unchecked. `-a`, `--ac`, `--acceptance-criteria` as for `append`. Other lines in the section are kept.

## `chreos task refs show`

```
chreos task refs show NAME [-P|--project PROJECT] [--json]
```

Prints the `## References` entries as `- …` lines; `--json` as `{text, kind}` objects with `kind` `link`, `url`, `item` (or `null` for a hand-written entry that is none of them).

## `chreos task refs append`

```
chreos task refs append NAME (-r TEXT)... [-P|--project PROJECT]
```

Adds references. `-r`, `--ref`: repeatable; each must be a Markdown link `[text](target)`, a URL `scheme://…`, or an item reference that resolves.

## `chreos task refs replace`

```
chreos task refs replace NAME (-r TEXT)... [-P|--project PROJECT]
```

Replaces all references. `-r`, `--ref` as for `append`.

## `chreos task notes show`

```
chreos task notes show NAME [-P|--project PROJECT] [--json]
```

Prints the `## Notes` entries as `- …` lines; `--json` as a list of strings.

## `chreos task notes append`

```
chreos task notes append NAME (-N TEXT)... [-P|--project PROJECT]
```

Adds notes at the end of the list. `-N`, `--note`: repeatable, at least one, single line each.

## `chreos task notes replace`

```
chreos task notes replace NAME (-N TEXT)... [-P|--project PROJECT]
```

Replaces all notes. `-N`, `--note` as for `append`.
