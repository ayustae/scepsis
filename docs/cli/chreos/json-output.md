# chreos — JSON Output

Reference for the JSON printed by `--json` (or by default with `output.format = "json"`): the shape of every JSON-producing command. These shapes are a stable contract for scripts and agents; fields may be added, but existing ones won't change meaning without a deliberate, documented change.

## Values

Frontmatter values are converted as follows: timestamps → ISO 8601 strings with `T` and offset (`"2026-09-21T10:00:00+02:00"`), dates → `"YYYY-MM-DD"`, missing optional values → `null`, mappings and lists as is. Unknown frontmatter fields written by hand are included unchanged. Paths are absolute strings.

## `project list`, `task list`, `decision list`

An array with one object per item: every frontmatter field, plus `path` (the item file).

```json
[
  {
    "name": "homepage",
    "title": "Redesign homepage",
    "summary": null,
    "project": "web",
    "phase": "open",
    "status": "todo",
    "source": {"type": "git", "path": "site"},
    "priority": "high",
    "due": "2026-10-15",
    "assignee": "claude",
    "labels": ["urgent"],
    "dependencies": ["task:cms"],
    "created": "2026-09-21T10:00:00+02:00",
    "updated": "2026-09-25T17:45:00+02:00",
    "path": "/home/me/ws/web/tasks/homepage/TASK.md"
  }
]
```

## `project show`

```json
{"frontmatter": {…}, "body": "\n# Website\n…", "path": "/home/me/ws/web/PROJECT.md"}
```

## `task show`, `decision show`

As `project show`, plus the dependency view:

```json
{
  "frontmatter": {…},
  "body": "…",
  "path": "…",
  "dependencies": [{"ref": "task:cms", "status": "done", "satisfied": true}],
  "dependents": ["task:tooling/launch"]
}
```

`dependencies` keeps the references as written; `status` is `null` when a reference doesn't resolve. `dependents` are qualified references (`kind:project/name`) of the items that depend on this one.

## Section `show` commands

| **Command** | **Shape** |
| --- | --- |
| `task ac show --json` | `[{"text": "Renders at 320px", "checked": false}]` |
| `task refs show --json` | `[{"text": "[Spec](https://x)", "kind": "link"}]` — `kind`: `link`, `url`, `item` or `null` |
| `task notes show --json` | `["Layout implemented"]` |

## `config show`, `config get`

`config show --json`: the configured keys as a nested object, e.g. `{"workspace": {"path": "~/ws"}, "defaults": {"project": "default"}}`. `config get KEY --json`: the value as a JSON string, or `null` when an optional key is unset.

## `check`

```json
{
  "findings": [
    {"severity": "error", "path": "/home/me/ws/web/tasks/homepage/TASK.md",
     "item": "task:web/homepage", "message": "dependency 'task:cms' does not resolve"}
  ],
  "errors": 1,
  "warnings": 0
}
```

`severity` is `error` or `warning`; `item` is `null` for findings about entries that aren't items (e.g. a stray folder).
