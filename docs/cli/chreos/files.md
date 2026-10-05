# chreos — Workspace Layout and File Formats

Reference for what chreos keeps on disk: the workspace folder layout and the Markdown-with-frontmatter formats of projects, tasks and decisions (fields, value sets, suggested body sections). These files are meant to be read and edited by people and agents directly; chreos tolerates hand edits and `chreos check` reports anything inconsistent.

## Layout

```
<workspace>/
├── .scepsis.lock                 # workspace lock (see README.md, Workspace lock)
└── <project>/
    ├── PROJECT.md
    ├── tasks/
    │   └── <task>/
    │       ├── TASK.md
    │       └── work/             # open tasks only: git worktree or symbolic link
    ├── .archive/
    │   └── <task>.md             # an archived task (its TASK.md, renamed)
    └── decisions/
        └── <decision>.md
```

- A project is a folder with a `PROJECT.md` and a valid name. Entries starting with `.` are ignored.
- Names come from the paths: a task's name is its folder (or archived file) name, a decision's its file name, and the owning project is the enclosing project folder. The `name` and `project` fields are caches of these; `chreos check --fix` repairs them when they drift.
- Missing `tasks/`, `.archive/` or `decisions/` folders are treated as empty and recreated on the next write.
- A closed task folder holds only `TASK.md`; an open one also holds `work/` and anything else the work needs.
- Task names are unique within a project across `tasks/` and `.archive/`; decision names within `decisions/`. A task and a decision may share a name.

## Common fields

Every file starts with a YAML frontmatter block between `---` lines.

| **Field** | **Type** | **Required** | **Notes** |
| --- | --- | --- | --- |
| `name` | name | yes | Cache of the path (see above). |
| `title` | text | yes | Defaults to the name. Rendered as the body's `# ` heading. |
| `summary` | text or `null` | no | Rendered as the paragraph under the heading. |
| `status` | enum | yes | Value set per item type, below. |
| `labels` | list | no | `key` or `key=value`, lowercase. |
| `created`, `updated` | timestamp | yes | ISO 8601 with UTC offset, e.g. `2026-09-21T10:00:00+02:00`. |

Unknown fields, comments and key order are preserved by every chreos write. When `title` or `summary` change through chreos, the body's heading and summary paragraph follow only if they still match the old value (otherwise a warning is printed).

## `PROJECT.md`

`status`: `active` (default) or `inactive`. Suggested body: `# <title>`, the summary, `## Description`.

## `TASK.md`

| **Field** | **Type** | **Required** | **Notes** |
| --- | --- | --- | --- |
| `project` | name | yes | Cache of the enclosing project. |
| `phase` | `closed` or `open` | yes | Whether the task can be worked on. |
| `status` | enum | yes | See below. |
| `source` | mapping or `null` | to open | `{type: git|local, path: …}`; `path` absolute, `~`, or relative to the configured base folder of its type. |
| `priority` | `low`, `medium`, `high`, `critical` or `null` | no | |
| `due` | date or `null` | no | `YYYY-MM-DD`. |
| `assignee` | text or `null` | no | A person or an agent. |
| `dependencies` | list of item references | no | Tasks or decisions this task depends on. |
| `archived` | timestamp | archived tasks only | Set by `task archive`, removed by `task restore`. |

Statuses allowed per phase:

| **Phase** | **Statuses** |
| --- | --- |
| `closed` | `new` (default), `done`, `cancelled` |
| `open` | `todo`, `on-hold`, `in-progress`, `done`, `cancelled` |

A dependency is **satisfied** when it points to a task that is `done` or `cancelled`, or to a decision that is `decided`. A task is **ready** when it is live, not `done`/`cancelled`, and all its dependencies are satisfied.

Suggested body sections, used by the section commands: `## Description`, `## Acceptance criteria` (`- [ ]` / `- [x]` lines), `## References` (one `- ` line per Markdown link, URL or item reference), `## Notes` (`- ` lines). Sections are found by exact `## ` heading outside fenced code; everything else in the body is free-form.

## Decision files (`decisions/<name>.md`)

Additional fields: `project` (cache) and `dependencies` (item references). `status`: `pending` (default) or `decided`. The body is free-form after the heading and summary.
