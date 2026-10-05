# idion — `idion check`

Reference for `idion check`, which validates the whole context tree and lists every problem. What each entry of the tree is treated as is in `files.md`; the JSON shape is in `json-output.md`.

## `idion check`

```
idion check [--json]
```

Scans the context tree and reports **errors** (something is wrong) and **warnings** (worth attention, tolerated). It only reads; nothing is fixed automatically.

| **Severity** | **Problem** |
| --- | --- |
| error | A file whose frontmatter can't be parsed, or that isn't valid UTF-8 |
| error | A missing, empty, multi-line or too long `description` (in a context file or an `_index.md`) |
| error | A file or folder whose name isn't a valid identifier segment (ignored with its contents) |
| error | An `_index.md` in the root |
| error | A folder nested deeper than 8 levels (ignored with its contents) |
| error | A folder that can't be read |
| warning | A folder with context files but no `_index.md` |
| warning | A file that isn't a context file (`notes.txt`, …) |
| warning | A symbolic link |
| warning | An empty folder |
| warning | A file and a folder with the same name (`atlas.md` and `atlas/`) |

The text output lists the problems as a table (severity, path relative to the root, identifier or `-`, message), errors first, then by path, followed by a summary:

```
error    broken.md  broken  no frontmatter: the file must start with a '---' line
warning  notes.txt  -       not a context file, ignored
warning  teams      teams/  no _index.md: the folder has no description
1 error, 2 warnings
```

A clean tree prints `no problems found`. The exit code is `1` if there is any error, `0` otherwise.

- `--json`: see `json-output.md`.
