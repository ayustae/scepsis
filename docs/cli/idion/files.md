# idion — Context Tree and File Format

Reference for what idion reads and writes: the context tree in `~/.scepsis/context/`, which entries are context files and folder descriptions, which are ignored or reported, and the file format. Commands are in `commands.md` and `folders.md`; problems are listed by `idion check` (`check.md`).

## The context tree

The context tree lives at the fixed path `~/.scepsis/context/`. `idion init` creates it with mode `0700` (readable only by the user) and never changes an existing one. Its folders are free-form: the user decides how to organise them.

```
~/.scepsis/context/
├── .idion.lock                       # write lock, never a context file
├── user.md                           # context file 'user'
├── teams/
│   ├── _index.md                     # description of the folder 'teams/'
│   └── my-team.md                    # context file 'teams/my-team'
└── company/
    ├── _index.md
    └── projects/atlas/architecture.md
```

| **Entry** | **Treated as** |
| --- | --- |
| `<name>.md` with a valid name | A context file; its identifier is its path without `.md` |
| `_index.md` in a folder | The folder's description |
| `_index.md` in the root | An error: the root has no description |
| A folder with a valid name, at most 8 levels deep | Part of the tree |
| A name starting with `.` (`.idion.lock`, `.git/`, …) | Ignored silently |
| A symbolic link | Ignored, reported as a warning |
| Any other file (`notes.txt`, …) | Ignored, reported as a warning |
| A file or folder with an invalid name, or a folder nested deeper than 8 levels | Ignored with its contents, reported as an error |

Folders with context files but no `_index.md`, empty folders, and a file and a folder sharing a name (`atlas.md` next to `atlas/`) are reported as warnings.

## File format

Context files and `_index.md` files have the same format: a YAML frontmatter between `---` lines, then a free Markdown body.

```markdown
---
description: Members, responsibilities and rituals of my team.
---

# My team

Free Markdown content.
```

| **Field** | **Type** | **Required** | **Rules** |
| --- | --- | --- | --- |
| `description` | string | yes | Non-empty, a single line without control characters, at most 200 characters. Values given on the command line are stripped of surrounding whitespace. |

- Other fields are allowed and kept.
- The body is free. A new context file gets `# <last segment>` unless a body is given; a new `_index.md` gets an empty body.
- Files are UTF-8. CRLF line endings are kept.

## What writes preserve

`update`, `append`, `replace` and `folder describe` change only what they are asked to: comments, key order, quoting and unknown fields are kept, and so is the body (byte-for-byte, including CRLF) except for the text `append` adds or the body `replace` sets. A trailing comment on the changed `description` line is kept, though the spaces before it may change. Files are written atomically (a temporary file renamed over the original) with their permissions kept. A file whose frontmatter can't be parsed is never rewritten: these commands refuse it with a hint to fix it with `idion edit` or by hand.
