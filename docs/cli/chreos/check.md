# chreos — `chreos check`

Reference for `chreos check`: what it validates across the workspace, how findings are classified as errors or warnings, the output, exit codes, and what `--fix` repairs. JSON output is described in `json-output.md`.

## `chreos check`

```
chreos check [--fix] [--json]
```

Validates the whole workspace and prints one line per finding (`severity  path  item  message`, paths relative to the workspace), then `N errors, M warnings`, or `no problems found`. Each finding names the command that fixes it where there is one.

- `--fix`: first rewrites the `name`/`project` fields that don't match the paths (nothing else), printing each fixed file on standard error, then checks.
- `--json`: see `json-output.md`.

Exit code `1` if there is at least one error, `0` otherwise (warnings only).

**Errors** (something is wrong):

- a file whose frontmatter can't be parsed;
- invalid field values (schema), including phase/status combinations;
- `name`/`project` fields that don't match the path;
- dependencies that don't resolve, and dependency cycles (each reported once);
- a task that is both live and archived;
- an archived task without `archived`, or a live task with it;
- an open task without `work/`, or with a broken link or worktree (`chreos task open --recreate` rebuilds it).

**Warnings** (worth attention, tolerated):

- entries that don't belong to the layout (folders without `PROJECT.md` at the root, stray files in `tasks/`, `.archive/`, `decisions/`);
- a body `# ` heading that differs from the title;
- files left in a closed task folder (`chreos task close` cleans them up);
- an `on-hold` task whose dependencies (it has some) are all satisfied, and a `todo` or `in-progress` task with unsatisfied dependencies — statuses never change on their own;
- task sources that don't resolve;
- item references in `## References` that don't resolve.
