# chreos — `chreos project`

Reference for the `chreos project` commands: creating, changing, listing, showing, editing, renaming and deleting projects, and their `## Description` section. Shared conventions (names, labels, `none`, `-f`, output, exit codes) are in `README.md`; the file format is in `files.md`.

## `chreos project create`

```
chreos project create NAME [-t TITLE] [-s SUMMARY] [-l LABEL]... [--status active|inactive]
```

Creates `<workspace>/NAME/` with `PROJECT.md`, `tasks/`, `.archive/` and `decisions/`, and prints the path of `PROJECT.md`.

- `-t`, `--title`: default NAME. `-s`, `--summary`. `-l`, `--label`: repeatable, comma-separated values accepted. `--status`: default `active`.

## `chreos project update`

```
chreos project update NAME [-t TITLE] [-s SUMMARY|none] [-l LABEL]... [--remove-label LABEL]... [--status active|inactive]
```

Changes the given fields; at least one option is required. `-t`, `--title`; `-s`, `--summary` (`none` clears it); `-l`, `--label` adds; `--remove-label` removes an exact match; `--status`.

## `chreos project list`

```
chreos project list [-l LABEL]... [-n TEXT] [-t TEXT] [-s TEXT] [-S TEXT] [--status S]... [--all] [--sort KEY] [--json]
```

Lists projects as `name  status  title` rows. By default only `active` projects are shown.

- `-l`, `--label`: `key` matches `key` and any `key=…`; `key=value` matches exactly; repeated means AND.
- `-n`, `--name` / `-t`, `--title` / `-s`, `--summary` / `-S`, `--search`: case-insensitive substring of the name, title, summary, or body.
- `--status`: repeatable (OR). `--all`: every status.
- `--sort`: `name` (default), `created`, `updated` or `status`; missing values last.
- `--json`: see `json-output.md`.

## `chreos project show`

```
chreos project show NAME [--json]
```

Prints `PROJECT.md` as it is; `--json` prints frontmatter, body and path.

## `chreos project edit`

```
chreos project edit NAME
```

Opens `PROJECT.md` in `$VISUAL`/`$EDITOR` (needs a terminal) and validates it afterwards: unchanged → problems shown as warnings; changed and valid → `updated` bumped; changed but unparseable → left as saved, exit `1`; changed with validation errors → `updated` bumped, errors shown, exit `1`. The edit is never reverted.

## `chreos project path`

```
chreos project path NAME
```

Prints the absolute path of `PROJECT.md`.

## `chreos project rename`

```
chreos project rename NAME NEW_NAME
```

Renames the folder, updates the `project` field of all its tasks and decisions, rewrites every cross-project reference (`task:NAME/…` → `task:NEW_NAME/…`), repairs the git worktrees of its open tasks, and updates `defaults.project` if it was the default project. Titles are not touched.

## `chreos project delete`

```
chreos project delete NAME [-f]
```

Deletes the project with all its tasks and decisions after a confirmation stating how many there are and which items elsewhere will lose references to them. Open tasks are cleaned up first (with their own safety prompt). References to the deleted items are removed from the remaining items. The default project can't be deleted. `-f`, `--force` skips the confirmations.

## `chreos project description show`

```
chreos project description show NAME
```

Prints the content of the `## Description` section.

## `chreos project description append`

```
chreos project description append NAME [TEXT]
```

Adds TEXT (or standard input) after the existing content, separated by a blank line. The text must not contain `# ` or `## ` heading lines or an unclosed code fence; `###` and deeper are fine. A missing section is recreated.

## `chreos project description replace`

```
chreos project description replace NAME [TEXT]
```

Replaces the content with TEXT (or standard input); empty text clears it. Same rules as `append`.
