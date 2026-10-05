# chreos — `chreos decision`

Reference for the `chreos decision` commands: creating, changing, listing, showing, editing, renaming, moving and deleting decisions, and the section commands (`description`). Shared conventions (NAME forms, `-P`, references, `-f`, output, exit codes) are in `README.md`; the file format is in `files.md`.

All commands taking NAME accept `-P`, `--project`.

## `chreos decision create`

```
chreos decision create NAME [-P|--project PROJECT] [-t TITLE] [-s SUMMARY] [-l LABEL]... [--dep REF]... [--status pending|decided] [-f]
```

Creates `decisions/NAME.md` and prints its path.

- `-t`, `--title` (default NAME), `-s`, `--summary`, `-l`, `--label` (repeatable, comma-separated accepted).
- `--dep`, `--depends-on`: repeatable item reference; each must resolve and must not create a dependency cycle.
- `--status`: default `pending`. `decided` with unsatisfied dependencies asks for confirmation; `-f`, `--force` skips it.

## `chreos decision update`

```
chreos decision update NAME [-P|--project PROJECT] [-t TITLE] [-s SUMMARY|none] [-l LABEL]... [--remove-label LABEL]...
                       [--status pending|decided] [--dep REF]... [--remove-dep REF]... [-f]
```

Changes the given fields; at least one option is required. `-t`, `--title`; `-s`, `--summary`; `-l`, `--label`; `--remove-label`; `--status`; `--dep`, `--depends-on` adds (checked like `create`); `--remove-dep` removes the dependency pointing at the same item (`decision:x` also removes `decision:PROJECT/x`). Becoming `decided` with unsatisfied dependencies (after the changes) asks for confirmation; `-f`, `--force` skips it.

## `chreos decision list`

```
chreos decision list [-P PROJECT | --all-projects] [-l LABEL]... [-n TEXT] [-t TEXT] [-s TEXT] [-S TEXT]
                     [--status S]... [--all] [--depends-on REF] [--sort KEY] [--json]
```

Lists decisions as `name  status  title` rows (`project/name` with `--all-projects`). By default only `pending` decisions are shown.

- `-P`, `--project` (default: the default project) or `--all-projects`.
- `-l`, `--label`, `-n`, `--name`, `-t`, `--title`, `-s`, `--summary`, `-S`, `--search`, `--status`, `--all`, `--sort` (`name`, `created`, `updated`, `status`): as for `project list`.
- `--depends-on REF`: only decisions that depend on REF (resolved against `-P` or the default project).
- `--json`: see `json-output.md`.

## `chreos decision show`

```
chreos decision show NAME [-P|--project PROJECT] [--json]
```

Prints the file, then a `Dependencies:` block (each reference with its status and `satisfied`/`unsatisfied`) and a `Dependents:` block (items that depend on this one). `--json` includes them as `dependencies` and `dependents`.

## `chreos decision description show`

```
chreos decision description show NAME [-P|--project PROJECT]
```

Prints the content of `## Description`, where a decision's context, options, recommendation and outcome go.

## `chreos decision description append`

```
chreos decision description append NAME [TEXT] [-P|--project PROJECT]
```

Adds TEXT (or standard input) after the existing content, separated by a blank line. No `# `/`## ` heading lines or unclosed code fences; `###` and deeper are fine (e.g. `### Context`, `### Options`, `### Recommendation`, `### Decision`). A missing section is recreated at the end of the body.

## `chreos decision description replace`

```
chreos decision description replace NAME [TEXT] [-P|--project PROJECT]
```

Replaces the content with TEXT (or standard input); empty text clears it.

## `chreos decision edit`

```
chreos decision edit NAME [-P|--project PROJECT]
```

Opens the file in `$VISUAL`/`$EDITOR` and validates it afterwards, as `project edit`, also checking that the dependencies resolve and form no cycle.

## `chreos decision path`

```
chreos decision path NAME [-P|--project PROJECT]
```

Prints the absolute path of the decision file.

## `chreos decision rename`

```
chreos decision rename NAME NEW_NAME [-P|--project PROJECT]
```

Renames the file, updates `name`, and rewrites every reference to it in `dependencies` and `## References` sections.

## `chreos decision move`

```
chreos decision move NAME PROJECT [-P|--project PROJECT]
```

Moves the decision to another project (the name must be free there) and updates `project`. References are rewritten in both directions so they keep pointing at the same items.

## `chreos decision delete`

```
chreos decision delete NAME [-P|--project PROJECT] [-f]
```

Deletes the file after a confirmation listing the items that will lose references to it; those references are removed. `-f`, `--force` skips the confirmation.
