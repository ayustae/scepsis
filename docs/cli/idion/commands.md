# idion — Commands

Reference for the idion commands on the context tree and its files: `init`, `create`, `show`, `list`, `update`, `append`, `replace`, `edit`, `move` and `delete`. Folder descriptions are in `folders.md` and validation in `check.md`. Shared conventions (identifiers, text input, output, exit codes, lock) are in `README.md`; the file format is in `files.md`.

## `idion init`

```
idion init
```

Creates `~/.scepsis/context/` with mode `0700` (and `~/.scepsis/` if missing) and prints `Created <path>`. If the folder exists, prints `<path> already exists` and changes nothing; if a file is in its place, fails.

## `idion create`

```
idion create ID -d DESC [-b TEXT | --body-file PATH]
```

Creates the context file `ID` and prints its path. Missing parent folders are created. The identifier, description and body are validated before anything is written; an existing file is never overwritten.

- `-d`, `--description`: required; see the rules in `files.md`.
- `-b`, `--body`: the body; `-` reads standard input. Default: `# <last segment>`.
- `--body-file`: read the body from a UTF-8 file.
- `-b` and `--body-file` exclude each other. A body may not contain NUL characters.

## `idion show`

```
idion show ID [--json]
```

Prints the context file exactly as it is on disk. Problems with it (frontmatter that can't be parsed, a missing or invalid description) are printed as warnings and don't change the exit code. A file that isn't valid UTF-8 is an error.

- `--json`: see `json-output.md`.

## `idion list`

```
idion list [PREFIX] [--depth N] [--folders] [-S TEXT] [--json]
```

Lists context files, one per line, as `<id> — <description>`, sorted by identifier. This is the listing meant to be loaded into an AI's context.

```
$ idion list --depth 1
company/ — Company documentation references, grouped by project. (2 files)
teams/ — My team and the other teams in the department. (2 files)
user — The user: role, background, working preferences.
```

- `PREFIX`: a folder identifier (`teams/`); default `/`. The folder must exist; it isn't listed itself. Identifiers are always printed in full.
- `--depth`: at least 1, counted below PREFIX. A file deeper than `N` levels is replaced by its folder at level `N`, shown with the folder's description and the number of files it stands for (`(1 file)`, `(N files)`). Without `--depth`, every file is listed.
- `--folders`: also list described folders that aren't collapsed (without a count).
- `-S`, `--search`: keep only files whose identifier or description contains TEXT, in any case. Applied before collapsing: collapsed folders count matching files only.
- `--json`: see `json-output.md`.

A file with a missing or invalid description is shown as `<id> — (invalid description)`; a collapsed folder without `_index.md` as `<id> — (no description) (N files)`. If the context tree has problems under PREFIX, one line `warning: N problems in the context tree; run 'idion check'` goes to standard error; the exit code stays `0`.

## `idion update`

```
idion update ID -d DESC
```

Sets the description of the context file `ID` and prints its path. Only the `description` line changes (see `files.md`); a missing or invalid description is repaired, and an unchanged value isn't rewritten.

- `-d`, `--description`: required.

## `idion append`

```
idion append ID -t TEXT
```

Appends a paragraph to the body of the context file `ID` and prints its path. The body's trailing blank lines are trimmed, then a blank line, the text and a final line break are added. Line breaks in the text are converted to the file's own (CRLF files stay CRLF). Blank text is refused. A file with an invalid description can still be appended to; the problem is printed as a warning.

- `-t`, `--text`: required; `-` reads standard input.

## `idion replace`

```
idion replace ID (-b TEXT | --body-file PATH)
```

Replaces the body of the context file `ID` and prints its path. The frontmatter is kept as it is (see `files.md`). The new body is laid out as `create` writes one: a blank line after the frontmatter, then the text with a final line break; an empty text clears the body. Line breaks in the text are converted to the file's own (CRLF files stay CRLF). An unchanged body isn't rewritten. A file with an invalid description can still be changed; the problem is printed as a warning. A file whose frontmatter can't be parsed is refused.

- `-b`, `--body`: the new body; `-` reads standard input.
- `--body-file`: read the new body from a UTF-8 file.
- Exactly one of `-b` and `--body-file` is required. A body may not contain NUL characters.

## `idion edit`

```
idion edit ID
```

Opens the context file `ID` in `$VISUAL` or `$EDITOR`, then validates it. With a folder identifier (`teams/`), opens the folder's `_index.md`.

| **After the editor exits** | **Result** |
| --- | --- |
| The file is unchanged | Its existing problems are printed as warnings; exit `0` |
| Changed and valid | Exit `0` |
| Changed, the frontmatter can't be parsed | The file is left as saved; an error says to run `idion edit ID` again; exit `1` |
| Changed, the description is missing or invalid | The errors are listed; exit `1` |

idion never writes, reverts or fixes the edited file. Without a terminal, `edit` fails with `edit needs a terminal; use 'idion replace' (body) or 'idion update' (description), or edit the file directly: <path>` (for a folder, it names `idion folder describe`).

## `idion move`

```
idion move SRC DST
```

Moves a context file to a new identifier (`idion move teams/my-team people/my-team`), or a folder with everything in it, `_index.md` included (`idion move company/ org/`), and prints the new path. Files move to files and folders to folders; the root can't be moved or be a destination, and a folder can't be moved into itself. `SRC` must exist and `DST` must not: nothing is ever overwritten. Missing parent folders of `DST` are created; folders emptied by the move are left in place (`idion check` reports them, `idion delete` removes them).

## `idion delete`

```
idion delete ID [-f]
```

Deletes the context file `ID`, or the folder `ID/` with everything in it, and prints `Deleted <path>`. It asks for confirmation first (see `README.md`). A folder holding anything besides its `_index.md` is refused unless `-f` is given; symbolic links inside it are removed, never followed. The root can't be deleted.

- `-f`, `--force`: don't ask; also required to delete a folder that isn't empty.
