# idion — JSON Output

Reference for the JSON printed by `--json` on `idion show`, `idion folder show`, `idion list`, `idion search` and `idion check`. These shapes are a stable contract for scripts and agents; fields may be added, but existing ones won't change meaning without a deliberate, documented change. JSON goes to standard output, indented, with non-ASCII characters kept as they are; warnings still go to standard error.

## `idion show --json` and `idion folder show --json`

An object:

```json
{
  "id": "teams/my-team",
  "path": "/home/user/.scepsis/context/teams/my-team.md",
  "frontmatter": {"description": "Members, responsibilities and rituals of my team."},
  "body": "\n# My team\n",
  "problems": []
}
```

| **Field** | **Contents** |
| --- | --- |
| `id` | The identifier; for `folder show`, the folder identifier (`teams/`) |
| `path` | Absolute path of the file (`…/_index.md` for a folder) |
| `frontmatter` | Every frontmatter field; YAML dates and timestamps become ISO 8601 strings. `null` if the frontmatter can't be parsed |
| `body` | Everything after the frontmatter; the whole file text if the frontmatter can't be parsed |
| `problems` | What is wrong with the file, as messages; empty when it is valid |

## `idion list --json`

An array of entries, sorted by identifier (`[]` when nothing matches):

```json
[
  {"id": "teams/", "kind": "folder", "description": "My team and the other teams.", "path": "/home/user/.scepsis/context/teams", "files": 2},
  {"id": "user", "kind": "file", "description": "The user: role, background, working preferences.", "path": "/home/user/.scepsis/context/user.md"}
]
```

| **Field** | **Contents** |
| --- | --- |
| `id` | The identifier, in full |
| `kind` | `file` or `folder` |
| `description` | The description; `null` for a file with a missing or invalid description, or a folder without one |
| `path` | Absolute path of the file or folder |
| `files` | Only on collapsed folders (`--depth`): how many context files the entry stands for |

## `idion search --json`

An array, one object per matching file, sorted by `id`:

```json
[
  {
    "id": "teams/other-team",
    "path": "/home/user/.scepsis/context/teams/other-team.md",
    "description": "Other team: members, what they own.",
    "lines": [
      {"line": 7, "text": "- Owns the ingestion pipelines since 2026-09."}
    ]
  }
]
```

| **Field** | **Value** |
| --- | --- |
| `id` | The file's identifier |
| `path` | Absolute path of the file |
| `description` | The description, or `null` when it is missing or invalid |
| `lines` | The body lines containing the text: `line` is the 1-based line number in the file, `text` the line without its line break. Empty when only the identifier or description matched. |

## `idion check --json`

An object:

```json
{
  "findings": [
    {"severity": "error", "path": "/home/user/.scepsis/context/broken.md", "id": "broken", "message": "no frontmatter: the file must start with a '---' line"},
    {"severity": "warning", "path": "/home/user/.scepsis/context/notes.txt", "id": null, "message": "not a context file, ignored"}
  ],
  "errors": 1,
  "warnings": 1
}
```

| **Field** | **Contents** |
| --- | --- |
| `findings` | Every problem, errors first, then by path |
| `findings[].severity` | `error` or `warning` |
| `findings[].path` | Absolute path of the entry |
| `findings[].id` | The identifier of the file or folder, or `null` for entries that have none (invalid names, other files, symbolic links) |
| `findings[].message` | What is wrong |
| `errors`, `warnings` | The counts |

The exit code of `idion check --json` is `1` when `errors` is not zero, as without `--json`.
