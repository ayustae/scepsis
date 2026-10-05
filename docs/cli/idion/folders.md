# idion — `idion folder`

Reference for the `idion folder` commands, which write and read a folder's description (`<folder>/_index.md`): the text `list --depth` shows for collapsed folders. Shared conventions are in `README.md`; the file format is in `files.md`. To edit an `_index.md` in an editor, use `idion edit FOLDER/` (`commands.md`).

## `idion folder describe`

```
idion folder describe FOLDER -d DESC
```

Sets the description of `FOLDER` (an identifier with a trailing `/`, such as `teams/`) and prints the path of its `_index.md`. Missing folders are created. A new `_index.md` gets only the frontmatter; an existing one changes like `idion update` changes a file (only the description, unchanged values aren't rewritten, unparseable frontmatter is refused). The root `/` has no description and is refused.

- `-d`, `--description`: required; see the rules in `files.md`.

## `idion folder show`

```
idion folder show FOLDER [--json]
```

Prints the folder's `_index.md` exactly as it is on disk, like `idion show` prints a file; problems are printed as warnings. A missing folder, or a folder without `_index.md`, is an error.

- `--json`: the same shape as `idion show --json`, with `id` set to the folder identifier (see `json-output.md`).
