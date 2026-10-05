# chreos — Data Model and Command Surface

System design for `chreos`, the Scepsis task manager CLI (`tools/chreos/`): the on-disk storage model for projects, tasks and decisions, the file format, the task lifecycle, and the proposed command interface, with the reasoning behind each decision. The command reference is in `docs/cli/chreos/`.

Status: implemented (`tools/chreos/`). Command reference: `docs/cli/chreos/`.

## 1. Guiding principle

Projects, tasks and decisions are Markdown files meant to be opened and edited by **humans and AI agents alike**, with any editor or file tool. The CLI is a convenience layer focused on the **frontmatter metadata**: creating items, changing metadata, driving the task lifecycle, archiving and deleting, and listing/searching. For task, project and decision bodies it offers only a few simple section commands (§9); anything more complex is done by opening the file. Consequently:

- The CLI never imposes a body structure and changes the body only in the cases listed in §8.
- The CLI must tolerate hand edits: missing optional fields, extra unknown fields, reordered keys, YAML comments, and arbitrary body content are all valid and must be preserved.
- A hand-broken file (invalid YAML, invalid field value) is reported, not fatal: commands keep working on every other item, and `chreos check` lists every problem.

## 2. Storage layout

The workspace is a plain directory tree (path configured in `~/.scepsis/config.toml`, see §13). No database.

```
workspace/
├── default/                            # default project, created by `chreos init`
│   ├── PROJECT.md
│   ├── tasks/
│   ├── .archive/
│   └── decisions/
└── website-relaunch/                   # a project (folder name = project name)
    ├── PROJECT.md
    ├── tasks/                          # live tasks
    │   ├── redesign-homepage/          # an open task (folder name = task name)
    │   │   ├── TASK.md
    │   │   └── work/                   #   git worktree or symlink, created by `task open`
    │   └── migrate-cms/                # a closed task
    │       └── TASK.md
    ├── .archive/                       # archived tasks of this project (always closed)
    │   └── old-newsletter-signup.md    #   a task's TASK.md, renamed; archived: 2026-09-01T10:12:00+02:00
    └── decisions/                      # project-wide decisions
        ├── hosting-provider.md         # a decision (file name = <decision name>.md)
        └── frontend-framework.md
```

Rules:

- A **project** is a folder directly under the workspace root that contains a `PROJECT.md`. Entries whose name starts with `.` are ignored; any other folder without `PROJECT.md` is ignored by commands and reported by `check`.
- A project contains `PROJECT.md` and the folders `tasks/`, `.archive/` and `decisions/`. `project create` creates all three; whenever the CLI finds one of them missing (e.g. removed by hand, or dropped by a tool that doesn't keep empty folders), it treats it as empty and recreates it on the next write. More project-level folders may be added later; keeping each kind of item in its own folder means they never collide.
- A live task is a folder inside `tasks/` containing a `TASK.md`. An archived task is a single file `.archive/<name>.md`: the task's `TASK.md`, renamed after the task (§7).
  - A **closed** task folder contains only `TASK.md`.
  - An **open** task folder also contains `work/` (§11), plus any other files the work needs (notes, attachments, artifacts). `task close` removes everything except `TASK.md`.
- A decision is a single Markdown file `decisions/<name>.md`. Decisions apply to the whole project. They are never archived.
- Items relate to each other only through `dependencies` (§6). There is no task hierarchy.
- There is no workspace-level archive. Projects are either live or deleted (§7).
- Project names follow the slug pattern (§5), so any workspace-level entry can use a name outside that pattern (e.g. starting with `.` or `_`) and never collide with a project. The only such entry today is the lock file `.scepsis.lock` (§12).

## 3. File format

All three file types are Markdown with a YAML frontmatter block. The suggested body structure is defined by the templates in `templates/` (rendered by `create`), but nothing enforces it.

### 3.1 Common fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | string | yes | Chosen by the user at creation (§5). Equals the folder or file name, which is authoritative (§4). |
| `title` | string | yes | Human-readable name. Defaults to `name` verbatim when not given. Also rendered as the body's H1 at creation. |
| `summary` | string | no | One or two sentences. Also rendered as the paragraph under the H1 at creation. Kept in frontmatter so list/search tools don't parse the body. |
| `status` | enum | yes | The value set depends on the item type (§10). |
| `labels` | list of strings | no | Bare key (`urgent`) or `key=value` (`language=python`); see §3.5. |
| `created` | timestamp | yes | ISO 8601 with UTC offset. Set by `create`. |
| `updated` | timestamp | yes | ISO 8601 with UTC offset. Bumped on every change the CLI makes, including edits made through `edit` (§12). Edits made outside the CLI cannot bump it; tools needing "last touched" regardless of editor can use the file's modification time. |

### 3.2 `PROJECT.md`

`status` is `active` (default) or `inactive`.

Suggested body: `# <title>`, the summary paragraph, `## Description`.

```markdown
---
name: website-relaunch
title: Website Relaunch
summary: Rebuild the public site on the new design system.
status: active
labels:
  - client=acme
created: 2026-09-20T09:00:00+02:00
updated: 2026-09-25T17:40:00+02:00
---

# Website Relaunch

Rebuild the public site on the new design system.

## Description

Scope, goals, stakeholders, links to the brief...
```

### 3.3 `TASK.md`

Additional fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `project` | string | yes | Owning project's name. The enclosing project folder is authoritative (§4). |
| `phase` | enum | yes | `closed` (default) or `open`: whether the task can be worked on (§11). |
| `source` | mapping or null | required to open | Where the work happens. `null` until set. |
| `source.type` | enum | with `source` | `git` (a git repository) or `local` (a plain folder). |
| `source.path` | string | with `source` | Absolute path (a leading `~` is allowed), or a path relative to the base folder configured for the type (§13). Stored exactly as given. |
| `priority` | enum or null | no | `low`, `medium`, `high` or `critical`. `null` means no priority. |
| `due` | date or null | no | Due date, `YYYY-MM-DD`. |
| `assignee` | string or null | no | Who is working on the task: a person or an agent (e.g. `alice`, `claude`). Free single-line text. |
| `dependencies` | list of strings | no | Item references (§6) to tasks or decisions this task depends on; may cross projects. |
| `archived` | timestamp | only when archived | Set when the task is moved to `.archive/`, removed on restore (§7). |

`status` is one of `new` (default), `todo`, `in-progress`, `on-hold`, `done`, `cancelled`; which values are allowed depends on the phase (§11).

Suggested body: `# <title>`, the summary paragraph, then:

- `## Description` — what and why.
- `## Acceptance criteria` — a GFM checkable task list (`- [ ]` / `- [x]`), one criterion per line, ticked by hand as criteria are verified.
- `## References` — links and pointers relevant to the task, one bullet per reference (§9): a Markdown link (`- [text](url-or-path)`), a bare URL (`- https://…`), or an item reference (`- task:migrate-cms`, `- decision:other-project/hosting`, §6).
- `## Notes` — a plain bullet list where humans and agents record progress, findings, and hand-off context.

```markdown
---
name: redesign-homepage
title: Redesign homepage
summary: New hero section and layout per the brand refresh.
project: website-relaunch
phase: open
status: in-progress
source:
  type: git
  path: website              # relative: resolved against the configured git base folder
priority: high
due: 2026-10-15
assignee: claude
labels:
  - urgent
  - area=frontend
dependencies:
  - task:migrate-cms
  - decision:frontend-framework
  - task:internal-tooling/build-cli
created: 2026-09-21T10:00:00+02:00
updated: 2026-09-25T17:45:00+02:00
---

# Redesign homepage

New hero section and layout per the brand refresh.

## Description

The current hero doesn't reflect the new brand...

## Acceptance criteria

- [x] Hero renders correctly at 320px and 1440px
- [ ] Lighthouse performance score >= 90
- [ ] Reviewed by a human

## References

- [Hero pattern](https://design-system.example.com/hero-pattern)
- https://web.dev/articles/lcp
- decision:hosting-provider

## Notes

- Layout implemented
- Performance at 82 because of the hero image size
```

### 3.4 Decision files (`decisions/<name>.md`)

A decision records a choice that affects the whole project: what was (or needs to be) decided, and why.

Additional fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `project` | string | yes | Owning project's name. The enclosing project folder is authoritative (§4). |
| `dependencies` | list of strings | no | Item references (§6) to decisions or tasks this decision depends on; may cross projects. |

`status` is `pending` (default: still to be made) or `decided` (made).

Suggested body: `# <title>`, the summary paragraph, `## Description`. The description is free-form; a common but optional shape is `###` subsections for the context, the options considered, the recommendation, the choice and its consequences. Anything outside `## Description` is free-form too.

```markdown
---
name: hosting-provider
title: Hosting provider
summary: Where the relaunched site will be hosted.
project: website-relaunch
status: decided
labels:
  - area=infra
dependencies:
  - decision:frontend-framework
  - task:cost-estimate
created: 2026-09-22T11:00:00+02:00
updated: 2026-09-26T09:30:00+02:00
---

# Hosting provider

Where the relaunched site will be hosted.

## Description

We compared provider A and provider B on cost, EU data residency and
static-site support. We chose provider B: it meets residency requirements
and the static build fits its free tier. Migration of DNS is tracked in
the `migrate-dns` task.
```

### 3.5 Labels

- Normalized to lowercase on write.
- Key: `[a-z0-9_-]+`. Value (optional, after a single `=`): non-empty, no whitespace, no commas, no further `=`.
- Several values for the same key are allowed (`language=python`, `language=go`).
- Duplicates are removed.

## 4. Source of truth and caches

Some facts are stored in the frontmatter as well as implied by the path, so a single file is self-describing (an agent reading one `TASK.md` or decision knows its name and project without walking the tree). Each has exactly one authoritative source:

| Fact | Authoritative source | Frontmatter copy |
| --- | --- | --- |
| Item name | live task folder name, or archived task / decision file name without `.md` | `name` (cache) |
| Owning project | enclosing project folder | `project` (cache) |
| Task archived or live | whether the task is in `tasks/` or `.archive/` | `archived` (records when) |
| Title, summary | frontmatter `title`, `summary` | body H1 / summary paragraph (rendered at creation; see §8) |

Hand edits (e.g. renaming a folder or file) can make caches stale. `chreos check` reports all drift; `chreos check --fix` rewrites **only** the caches (`name`, `project`), never titles, summaries, or body content.

## 5. Names

`name` is chosen by the user as the `create` command's positional argument. It is **validated, not sanitized**: an invalid name is rejected with an explanatory error, never silently rewritten.

- Pattern: `^[a-z0-9]+(-[a-z0-9]+)*$` (lowercase alphanumeric segments separated by single hyphens).
- Maximum length: 64 characters.
- Collisions are an error; the user picks another name.
- `title` defaults to `name` verbatim when `--title` is omitted.
- A task's name is also the name of its git branch (§11.3).

## 6. Uniqueness, references and dependencies

**Uniqueness:**

- Project names are unique in the workspace.
- Task names are unique within their project, **across both `tasks/` and `.archive/`**. `create` and `restore` fail on a clash.
- Decision names are unique within their project's `decisions/`.
- Tasks and decisions are separate namespaces: a task and a decision in the same project may share a name.

**Item references** in `dependencies` and in the task `## References` section (and in `--dep`/`--remove-dep`/`--ref` values) always carry a kind prefix, so every entry says what it points to:

| Reference | Points to |
| --- | --- |
| `task:<name>` | a task in the same project |
| `task:<project>/<name>` | a task in another project |
| `decision:<name>` | a decision in the same project |
| `decision:<project>/<name>` | a decision in another project |

- "Same project" means the project of the item holding the reference.
- A reference without a prefix is rejected with a hint (e.g. "did you mean `task:migrate-cms`?").
- Command NAME arguments do **not** take a prefix, because the command already names the kind: `chreos task show <name>` or `<project>/<name>`, `chreos decision show <name>` or `<project>/<name>`. The qualified form makes `-P` unnecessary.

**Resolution** is a direct path lookup:

- `task:` → `<project>/tasks/<name>/TASK.md`, then `<project>/.archive/<name>.md`. Because archived tasks still resolve, archiving never breaks a reference.
- `decision:` → `<project>/decisions/<name>.md`.

**Dependencies** form a single graph over tasks and decisions across all projects. Any item may depend on any task or decision:

- The CLI checks that every reference resolves when writing it.
- It refuses additions that would create a cycle anywhere in the graph.
- `check` reports unresolved references and cycles created by hand edits.
- A dependency is **satisfied** when it points to a task with status `done` or `cancelled`, or to a decision with status `decided`. `task open` uses this to choose between `todo` and `on-hold` (§11.3); setting a task to `done` or a decision to `decided` with unsatisfied dependencies asks for confirmation (§10).

**Item references in `## References`** (§9) are pointers, not dependencies: they are not part of the graph, may form cycles, and don't affect satisfaction or readiness. Otherwise they are handled like dependencies: checked to resolve when written through `task refs`, rewritten by rename and move, removed when their target is deleted (§7), and reported by `check` when unresolved.

**Next-action view** — computed on demand, never stored:

- A task is **ready** when it is live (not archived), its status is not `done` or `cancelled`, and every dependency is satisfied. `task list --ready` lists ready tasks: the answer to "what can be worked on next?".
- The **dependents** of an item are the tasks and decisions that list it in their `dependencies`, found by scanning the workspace.
- `task show` and `decision show` display each dependency with its status and whether it is satisfied, and the item's dependents. `task list` and `decision list` accept `--depends-on REF` to find the items that depend on a given one.

## 7. Archive, deletion, renaming and moving

**Tasks** can be archived (reversible) or deleted (permanent).

- `task archive` works on **closed** tasks (§11), whatever their status (`new`, `done` or `cancelled`), so no working folder ever ends up in `.archive/`. Files left by hand in a closed task's folder are removed first, with the cleanup safety prompt (§11.4). Archiving is only ever done by hand; nothing archives tasks automatically, and archived tasks are kept until deleted.
- An archived task is a single file: `task archive` moves `P/tasks/T/TASK.md` to `P/.archive/T.md`, removes the now empty `P/tasks/T/`, and sets `archived` in the frontmatter. No confirmation: it's reversible, and references to the task keep resolving. Its `dependencies`, and other items' references to it, are left untouched.
- On an **open** task, `task archive` fails with a hint to close it first. With `-f`, it runs `task close` first (with `--status` if given, skipping its confirmations, and failing like `close` if the task doesn't end up `done` or `cancelled`), then archives it.
- `task restore` recreates `P/tasks/T/TASK.md` from `P/.archive/T.md` and removes `archived`. The task stays closed; open it with `task open`.
- **Archived tasks are read-only.** Only `show`, `path`, `list --archived`, `restore`, `delete`, `rename` and `move` work on them. Every other task command (`update`, `open`, `close`, `edit`, the section commands) fails with a hint to restore the task first.
- `task delete` permanently removes the task, live (its folder) or archived (its file). It asks for confirmation (§12). If the task is open, the `close` cleanup (§11.4) runs first, with its safety checks, so a git worktree is removed properly.

**Decisions** are records and are never archived. `decision delete` permanently removes the file, after confirmation.

**Projects** cannot be archived. A finished project is set to `inactive`, and can at most be deleted. `inactive` has no effect on the project's tasks and decisions.

- `project delete` permanently removes the project folder, including `tasks/`, `.archive/` and `decisions/`. It asks for confirmation, stating how many tasks and decisions will be removed. The `close` cleanup runs first for every open task.
- The default project cannot be deleted.

**Consistency:** these operations change several files and are not transactional. If one is interrupted, `chreos check` reports the stale references or caches it left behind.

**Reference cleanup:** whenever tasks or decisions are deleted (individually or with their project), every remaining task and decision that references them has those entries removed: from `dependencies`, and from the task `## References` section (§9). This is the only time the CLI removes references. The confirmation prompt lists the affected items.

**Renaming** (`project|task|decision rename NAME NEW_NAME`) changes an item's name everywhere it is used. The new name must be valid (§5) and free in its namespace (§6). Titles are not touched. Every file changed by a rename has `updated` bumped. References are rewritten both in `dependencies` and in `## References` sections.

- **Task** (live or archived): moves the task folder (or the archived file), updates its `name`, and rewrites every reference to it (`task:<old>` within its project, `task:<project>/<old>` elsewhere) across the workspace. If a git branch with the old name exists in its source repository, it is renamed with `git branch -m` (refused, before anything changes, if a branch with the new name already exists; if the source doesn't resolve, the branch is left alone with a warning). Refused while the task is open, because its worktree is checked out on that branch; close it first.
- **Decision:** renames the file, updates its `name`, and rewrites every reference to it.
- **Project:** moves the project folder, updates the `project` field of all its tasks and decisions, rewrites every cross-project reference (`task:<old>/…`, `decision:<old>/…`), and updates `defaults.project` in the config if it is the default project. For open git tasks, it runs `git worktree repair` with their new `work/` paths; symbolic links of open local tasks keep working because they point to absolute paths. Branch names don't change.

**Moving** (`task|decision move NAME PROJECT`) relocates a task or decision to another project, keeping its name. The name must be free in the destination's namespace (§6). Every file changed by a move has `updated` bumped.

- **Task** (live or archived): moves the task folder (live) or the archived file (into the destination's `.archive/`) and updates its `project`. Refused while the task is open; close it first. The git branch is not changed.
- **Decision:** moves the file into the destination's `decisions/` and updates its `project`.
- **References** are rewritten so they keep pointing at the same items, in `dependencies` and in `## References` sections:
  - in the moved item, references to items of the old project gain the old project's prefix (`task:x` → `task:<old>/x`), and references to items of the destination lose it (`task:<dest>/x` → `task:x`);
  - references to the moved item from its old project gain the destination's prefix (`task:<name>` → `task:<dest>/<name>`), references from the destination lose the prefix (`task:<old>/<name>` → `task:<name>`), and references from any other project change project (`task:<old>/<name>` → `task:<dest>/<name>`).

## 8. Body ownership

The CLI changes a file's body only:

1. at `create`, by rendering the item's template (see "Templates" below);
2. when `update --title`/`--summary` changes the frontmatter value, it also replaces the body's H1 line or summary paragraph **only if they still match the old value exactly**. Otherwise the body is left untouched and the CLI prints a warning. The H1 is the first `# ` line outside fenced code; the summary paragraph is the paragraph right after it, unless that is a heading. Setting a summary on an item that had none inserts the paragraph after the H1 (if no paragraph is there yet); clearing it (`--summary none`) removes the paragraph if it still matches;
3. through the section commands (§9), each of which touches only its own section.

Everything else in the body is preserved byte-for-byte. The CLI **reads** the body for `--search`, `show`, the section `show` commands, the acceptance-criteria confirmation when a task becomes `done` (§10), and `check` (warnings only, e.g. H1 differs from `title`).

For anything the commands don't cover, the CLI gets people and agents to the file: `show` prints it, `edit` opens it in `$VISUAL`/`$EDITOR` and validates it afterwards (§12), and `path` prints its absolute path so agents can use their own file tools.

Frontmatter round-trip is non-destructive: the CLI changes only the keys a command targets and preserves comments, key order and unknown keys (implementation: `ruamel.yaml` in round-trip mode). Writes are atomic (write to a temporary file in the same directory, then rename).

**Templates:**

- The templates (`PROJECT.md`, `TASK.md`, `DECISION.md`) ship inside the CLI package; the repository's `templates/` folder is their source.
- A user can override any of them by placing a file with the same name in `~/.scepsis/templates/`. An override must keep the frontmatter keys of the original.
- Placeholders (`<name>`, `<title>`, …) are replaced at creation. Frontmatter values are set as YAML data, never by text substitution, so any title or summary stays valid YAML; a placeholder the CLI doesn't know is an error. An optional value that wasn't given is written as `null` (or `[]` for lists), and the body's summary paragraph is omitted when there is no summary.

## 9. Section commands

Four sections of `TASK.md`, one of `PROJECT.md` and one of decision files get dedicated commands, each with `show`, `append` (like `>>` on a file) and `replace` (like `>`):

| Section | Command group | Content |
| --- | --- | --- |
| `## Description` (task) | `chreos task description` | Free Markdown text. |
| `## Acceptance criteria` | `chreos task ac` | One `- [ ] <text>` line per criterion. |
| `## References` | `chreos task refs` | One `- <reference>` line per reference: a Markdown link, a bare URL, or an item reference (§3.3, §6). |
| `## Notes` | `chreos task notes` | One `- <text>` line per note. |
| `## Description` (project) | `chreos project description` | Free Markdown text. |
| `## Description` (decision) | `chreos decision description` | Free Markdown text: context, options, recommendation, outcome. |

Archived tasks are read-only (§7): only the `show` subcommands work on them.

```
chreos project description show NAME
chreos project description append NAME [TEXT]
chreos project description replace NAME [TEXT]

chreos decision description show NAME [-P PROJECT]
chreos decision description append NAME [TEXT] [-P PROJECT]
chreos decision description replace NAME [TEXT] [-P PROJECT]

chreos task description show NAME [-P PROJECT]
chreos task description append NAME [TEXT] [-P PROJECT]
chreos task description replace NAME [TEXT] [-P PROJECT]

chreos task ac show NAME [-P PROJECT] [--json]
chreos task ac append NAME (-a|--ac|--acceptance-criteria TEXT)... [-P PROJECT]
chreos task ac replace NAME (-a|--ac|--acceptance-criteria TEXT)... [-P PROJECT]

chreos task refs show NAME [-P PROJECT] [--json]
chreos task refs append NAME (-r|--ref TEXT)... [-P PROJECT]
chreos task refs replace NAME (-r|--ref TEXT)... [-P PROJECT]

chreos task notes show NAME [-P PROJECT] [--json]
chreos task notes append NAME (-N|--note TEXT)... [-P PROJECT]
chreos task notes replace NAME (-N|--note TEXT)... [-P PROJECT]
```

Examples:

```
chreos task description append redesign-homepage "Also cover the dark theme."

chreos task description replace website-relaunch/redesign-homepage <<'EOF'
The current hero doesn't reflect the new brand.

### Constraints

Must reuse the existing grid.
EOF

chreos task ac append redesign-homepage -a "Lighthouse >= 90" --ac "Reviewed by a human"
chreos task ac replace redesign-homepage -a "Hero renders at 320px" -a "Hero renders at 1440px"
chreos task notes append redesign-homepage -N "Layout implemented" -N "Perf at 82"
chreos task ac show redesign-homepage --json
chreos task refs append redesign-homepage -r "[Hero pattern](https://design-system.example.com/hero-pattern)" \
    -r https://web.dev/articles/lcp -r decision:hosting-provider
chreos project description append website-relaunch "Launch target: end of Q4."
```

Rules:

- **Text input for `description`** (task and project): the TEXT argument, or standard input when TEXT is omitted, which makes heredocs (`<<'EOF' ... EOF`) and pipes work. If TEXT is omitted and stdin is a terminal, the command fails with a usage hint.
- **Description content** must not contain H1 or H2 heading lines (`# ` or `## `) or an unclosed code fence, because they would break section boundaries; H3 and deeper, and any heading-like line inside a fenced code block, are fine. `description replace` with empty text clears the section. `append` adds the text after the existing content, separated by a blank line.
- **Acceptance criteria, references and notes** are single-line strings, one per repeated option; values containing line breaks are rejected. At least one value is required.
- `ac replace` rewrites the whole list, with every criterion unchecked. `refs replace` and `notes replace` rewrite the whole list. Ticking criteria (`- [x]`), reordering and other fine-grained edits are done by hand in the file.
- **References** must each be a Markdown link (`[text](target)`), a URL (`scheme://…`), or a prefixed item reference (§6); anything else is rejected, with the same hint as for dependencies when it looks like an unprefixed item name. Item references must resolve (§6).
- **Locating sections:** by an exact H2 heading match (`## Description`, `## Acceptance criteria`, `## References`, `## Notes`) at the start of a line, ignoring lines inside fenced code blocks. A section runs until the next H2 or the end of the file. For `ac`, `refs` and `notes`, only list items (`- [ ]`, `- [x]`, `- `) are read and written; other lines in the section are preserved.
- **Missing sections:** `append` and `replace` recreate a missing section in its template position: after the nearest preceding section of the template order (Description, Acceptance criteria, References, Notes for tasks) that exists; if none precedes it, before the nearest following one; if none of them exists, at the end of the file.
- **Output:** `description show` prints the raw section content. `ac show`, `refs show` and `notes show` print the list items as Markdown lines (`- [ ] …`, `- …`); with `--json` they return a list of strings (acceptance criteria as objects `{"text": ..., "checked": ...}`, references as objects `{"text": ..., "kind": "link"|"url"|"item"}`, with `kind` `null` for a hand-written entry that isn't a valid reference).
- Every `append`/`replace` bumps `updated`.

## 10. Status semantics

Every item has a `status`.

**Projects:**

| Status | Meaning |
| --- | --- |
| `active` | Being worked on. Default. |
| `inactive` | Not being worked on: paused or finished. Hidden from `project list` by default. |

**Decisions:**

| Status | Meaning |
| --- | --- |
| `pending` | The decision still has to be made. Default. |
| `decided` | The decision has been made. Hidden from `decision list` by default. |

**Tasks** (allowed values per phase in §11.1):

| Status | Meaning |
| --- | --- |
| `new` | Captured, never opened. Default. |
| `todo` | Open and ready to be worked on. |
| `on-hold` | Open, but paused: waiting on unsatisfied dependencies or something external, or deprioritized. May go straight to `in-progress`. |
| `in-progress` | Open and being worked on. |
| `done` | Finished and accepted. |
| `cancelled` | Will not be done. |

Whenever a task is set to `done` (by `update`, `open`, `close` or `archive -f`) while unchecked acceptance criteria (`- [ ]`) remain or dependencies are unsatisfied (§6), the CLI asks for confirmation in a single prompt, stating how many criteria are unchecked and listing the unsatisfied dependencies; `-f/--force` skips it. Likewise, setting a decision to `decided` (by `create` or `update`) while its dependencies are unsatisfied asks for confirmation, listing them; `-f` skips it. This encodes Scepsis's principle that work — especially an AI's — is verified before it's accepted.

Status changes between other values are not restricted beyond the phase rules of §11.1 (e.g. `on-hold` → `in-progress` is allowed with unsatisfied dependencies; `check` reports such inconsistencies, §11.5).

## 11. Task lifecycle

A task has a **phase** (can it be worked on?) and a **status** (where is the work?). `task open` turns a task's folder into a place to work; `task close` tears that down again.

```
  create
    │
    ▼
┌──────────────────┐   open    ┌──────────────────────────────────────┐
│ closed           │ ────────▶ │ open                                 │
│ status: new      │           │ status: todo | on-hold | in-progress │
└──────────────────┘           │         | done | cancelled           │
    │                          │ work/ exists                         │
    │ update --status          └──────────────────────────────────────┘
    │ cancelled | done                 │ close (status must be done or cancelled;
    ▼                                  │        work/ and other files removed)
┌──────────────────┐                   │
│ closed           │ ◀─────────────────┘
│ status: done |   │
│   cancelled      │ ── open (reopen) ──▶ open, status recomputed or given
└──────────────────┘
```

### 11.1 Phases and allowed statuses

| Phase | Meaning | Allowed statuses | Task folder |
| --- | --- | --- | --- |
| `closed` | Cannot be worked on. Default. | `new`, `done`, `cancelled` | only `TASK.md` |
| `open` | Can be worked on. | `todo`, `on-hold`, `in-progress`, `done`, `cancelled` | `TASK.md`, `work/`, anything else the work needs |

- A new task is `closed` with status `new`. `task create` takes no `--status`.
- `task update --status` refuses a value that isn't allowed in the current phase, and points to `open`/`close` instead. So a never-opened task can be cancelled with `update --status cancelled`, but not set to `todo`.
- Only `closed` tasks can be archived; `archive -f` closes an open task first (§7).

### 11.2 Source

`source` tells `open` where the work happens:

- `type: git` — `source.path` points to a git repository (anywhere inside it; the repository root is found with `git rev-parse --show-toplevel`). Requires git ≥ 2.30 (the first version with `git worktree repair`, used by project rename, §7); the CLI checks the version before running any git command. The CLI never pushes branches: publishing work is done with git in `work/`.
- `type: local` — `source.path` points to a plain folder.
- `source.path` is used as-is when absolute (a leading `~` is expanded). A relative path is resolved against the base folder configured for its type (`source.git_path` or `source.local_path`, §13). Relative paths stay relative in the frontmatter, so changing a base folder relocates every task that uses it.
- `source` is optional at `create`, so a task can be captured before its repository or folder is known, but **required to open** the task.
- `create`/`update` only warn when the path doesn't resolve (missing base folder, missing directory, not a git repository); `open` fails in those cases.
- The source of an open task cannot be changed; close it first.

### 11.3 `task open`

On a **closed** task:

1. Validate `source` (§11.2).
2. Create `work/`:
   - **git:** run `git worktree prune` in the repository (clearing leftovers of a hand-removed `work/`). Use the branch named after the task if it exists; otherwise create it from `--base REF` (default: the repository's default branch, i.e. `origin/HEAD` when that is set, else the current `HEAD`). Then `git worktree add <task folder>/work <task-name>`. If the branch is already checked out in another worktree (e.g. a same-named task in another project using the same repository), `open` fails with a clear message.
   - **local:** `work/` is a symbolic link to the resolved `source.path`.
3. Set `phase: open`.
4. Set the status: the `--status` value if given (`todo`, `on-hold`, `in-progress`, `done`, `cancelled`); otherwise `todo` when every dependency is satisfied (§6), else `on-hold`.

This also reopens a task that was closed as `done` or `cancelled`: the branch is reused and the status is recomputed (or taken from `--status`).

On an **open** task:

- If `work/` is missing (e.g. removed by hand), it is recreated as above.
- With `--recreate`, `work/` is removed (with the safety check of §11.4) and recreated.
- Otherwise `work/` is left untouched.
- `--status`, if given, is applied; the status is not recomputed otherwise.

### 11.4 `task close`

On an **open** task:

1. If `--status done|cancelled` is given, set it (with the confirmation for `done`, §10).
2. If the status is not `done` or `cancelled`, fail.
3. Clean up: remove everything in the task folder except `TASK.md`.
   - **git `work/`:** `git worktree remove`, then `git worktree prune`. The **branch is kept**: committed work lives there (e.g. for review or merging).
   - **local `work/`:** the symbolic link is removed. The target folder is **never** entered or deleted.
   - Any other files and folders are deleted.
4. Set `phase: closed`.

On an **already closed** task, `close` only re-runs the cleanup (step 3). `--status` is ignored with a warning.

**Safety check:** the cleanup (and `open --recreate`, which only touches `work/`) asks for confirmation when something would be lost: a git worktree with uncommitted or untracked changes, a `work/` that is neither a symbolic link nor a working git worktree (e.g. a plain folder or a broken worktree), or files in the task folder other than `TASK.md` and `work/`. The prompt lists them. Opening a closed task runs the same cleanup first, in case files were left in its folder by hand. `-f/--force` skips the confirmation (and forces `git worktree remove`); without a terminal and without `-f`, the command fails.

### 11.5 Keeping statuses current

Statuses never change on their own: when a dependency becomes `done`, tasks that depend on it stay `on-hold` until someone updates them (`task update --status todo`) or reopens them. `chreos check` reports:

- `on-hold` tasks that have dependencies, all satisfied (an `on-hold` task without dependencies may be waiting on something external), and `todo` or `in-progress` tasks with unsatisfied dependencies;
- phase/status combinations not allowed by §11.1;
- open tasks without `work/`, and closed tasks with anything besides `TASK.md`;
- anything in `.archive/` other than `<name>.md` files, and archived tasks whose name clashes with a live task;
- tasks in `.archive/` without an `archived` timestamp, and live tasks that have one;
- broken worktrees or links (e.g. after moving the workspace or the repository), which `open --recreate` repairs;
- sources that don't resolve;
- item references in `## References` sections that don't resolve (§6).

## 12. Proposed CLI interface

This is the proposed interface for implementation, not user reference documentation (see `docs/cli/chreos/`).

Conventions:

- Every command and subcommand accepts `-h/--help`; the root accepts `-V/--version`.
- `--project` is always `-P`.
- `-f/--force` always means "don't ask, just do it": it skips every confirmation (deletions, cleanup of a task folder, a task becoming `done` with unchecked criteria or unsatisfied dependencies, a decision becoming `decided` with unsatisfied dependencies, reassigning a task, overwriting the config in `init`). On `task archive`, it also closes an open task first (§7).
- `-n` is always `--name` (a list filter); `-N` is `--note`; `-r` is `--ref`.
- Options that clear an optional scalar field take the value `none` (e.g. `--summary none`, `--priority none`, `--due none`, `--assignee none`).
- `-l/--label` values may hold several comma-separated labels on `create` and `update` alike. On `update`, `--remove-label` is applied after `-l`, so a label given to both ends up removed.
- A command that needs confirmation and runs without a terminal (e.g. called by an agent) **fails** instead of waiting for input, unless `-f` is given. `edit` fails without a terminal, with a hint naming the group's `update` and section commands, and `path` to edit the file directly.
- Every `list`/`show` supports `--json`; default output is human-readable. The JSON output is a stable contract for scripts and agents, documented in the reference docs:
  - `list` returns an array of objects, each with the item's frontmatter fields plus `path` (absolute path of its file);
  - `show` returns an object with `frontmatter`, `body`, `path`, and for tasks and decisions the computed `dependencies` (each with `ref`, `status`, `satisfied`) and `dependents` (§6).
- **Workspace lock:** every command that writes holds an exclusive OS file lock on `<workspace>/.scepsis.lock` for its whole duration, so concurrent CLI calls (e.g. several agents) never overwrite each other's changes. A second writer waits up to 10 seconds, then fails with exit `1`. Read-only commands don't lock.
- Exit codes: `0` success; `1` user or validation error (not found, invalid name, refused or unconfirmed operation); `2` usage error (Click's default).
- List filters: `-n/--name`, `-t/--title`, `-s/--summary` and `-S/--search` are case-insensitive substring matches on name, title, summary, and body respectively. `-l key` matches `key` and any `key=*`; `-l key=value` matches exactly; repeated `-l` is a logical AND. `--status` and `--phase` are repeatable (logical OR).
- `--dep`/`--remove-dep` values are prefixed item references (§6); `--ref` values may also be one (§9). `--remove-dep` matches by the item a reference points to, so `task:x` also removes `task:<own project>/x`.
- `--assignee none` clears the assignee; only replacing one assignee with another counts as reassigning.
- On a closed task with a source, `update` may change `--source-type` or `--source-path` alone; without a source both are required.
- `list --all-projects` shows tasks as `<project>/<name>`; `--sort` ties (and `name`) order by project, then name.
- `edit` behavior (`project edit`, `task edit`, `decision edit`):
  1. Before launching `$VISUAL`/`$EDITOR`, the CLI records a hash of the file.
  2. When the editor exits, the CLI re-reads the file and runs the same per-file checks as `check`: frontmatter parses, required fields present, valid status/phase/priority/due/label values, dependencies resolve without cycles, item references in `## References` resolve, `name`/`project` caches match the path, body warnings (e.g. H1 differs from `title`).
  3. Unchanged file: nothing is written; existing problems are reported as warnings; exit `0`.
  4. Changed and valid: `updated` is bumped (non-destructive round-trip, atomic write); warnings are reported; exit `0`.
  5. Changed but the frontmatter doesn't parse: the file is left exactly as saved (`updated` can't be written safely); the error is reported with a hint to run `edit` again; exit `1`.
  6. Changed, parses, but has validation errors: `updated` is still bumped; the errors are reported; exit `1`. The CLI never reverts or "fixes" the edit.
  7. Only the edited file is validated; effects on other items are left to `check`.

### 12.1 Root and setup

```
chreos [-h|--help] [-V|--version]

chreos init [OPTIONS]
  --workspace-path PATH       prompted if omitted (interactive only)
  --default-project NAME      default: default; created if it doesn't exist
  --source-git-path PATH      base folder for relative git sources (optional)
  --source-local-path PATH    base folder for relative local sources (optional)
  -f, --force                 overwrite an existing config.toml without asking

chreos config show [--json]
chreos config get KEY [--json]         KEY is dotted, e.g. source.git_path
chreos config set KEY VALUE            validated as in §13; `none` removes an optional key

chreos check [OPTIONS]           validate the whole workspace: frontmatter schema of projects,
                               tasks and decisions, caches, dependencies (resolution and
                               cycles), name uniqueness, task lifecycle (§11.5), body warnings
  --fix                        rewrite stale caches (name, project) only
  --json
```

`check` reports **errors** (something is wrong: unparseable or invalid files, stale caches, unresolved dependencies, cycles, a task both live and archived, a wrong `archived` field, an open task without a working `work/`) and **warnings** (worth attention but tolerated: entries outside the layout, a body H1 that differs from the title, leftovers in a closed task folder, statuses that contradict the dependencies, sources that don't resolve, unresolved `## References` entries). It exits `1` if there is any error, `0` otherwise. `--fix` reports each file whose caches it rewrote, then runs the check. The JSON output is `{"findings": [{"severity", "path", "item", "message"}], "errors": N, "warnings": M}`.

### 12.2 `chreos project`

```
chreos project create NAME [OPTIONS]
  -t, --title TEXT             default: NAME
  -s, --summary TEXT
  -l, --label TEXT             repeatable; comma-separated values also accepted
  --status [active|inactive]   default: active

chreos project update NAME [OPTIONS]
  -t, --title TEXT
  -s, --summary TEXT
  -l, --label TEXT             repeatable, adds
  --remove-label TEXT          repeatable, removes (exact match)
  --status [active|inactive]

chreos project delete NAME [-f|--force]
chreos project rename NAME NEW_NAME       see §7

chreos project list [OPTIONS]
  -l, --label TEXT             repeatable, AND
  -n, --name TEXT
  -t, --title TEXT
  -s, --summary TEXT
  -S, --search TEXT
  --status [active|inactive]   repeatable, OR; default: active only
  --all                        include every status
  --sort [name|created|updated|status]   default: name
  --json

chreos project show NAME [--json]
chreos project edit NAME
chreos project path NAME

chreos project description ...     see §9
```

Examples:

```
chreos project create website-relaunch -t "Website Relaunch" -s "Rebuild the public site" -l client=acme
chreos project update website-relaunch --status inactive
chreos project list -l client=acme --sort updated --json
chreos project delete legacy-intranet -f
chreos project rename website-relaunch website-2026
chreos project description replace website-relaunch < brief.md
```

### 12.3 `chreos task`

```
chreos task create NAME [OPTIONS]
  -P, --project TEXT           default: config's default project
  -t, --title TEXT             default: NAME
  -s, --summary TEXT
  -l, --label TEXT             repeatable; comma-separated values also accepted
  --source-type [git|local]    set together with --source-path
  --source-path PATH           absolute, or relative to the configured base folder
  --priority [low|medium|high|critical]
  --due DATE                   YYYY-MM-DD
  --assignee TEXT
  --dep, --depends-on REF      repeatable; task:… or decision:…
                               (new tasks are always closed with status `new`)

chreos task update NAME [OPTIONS]
  -P, --project TEXT
  -t, --title TEXT
  -s, --summary TEXT
  -l, --label TEXT             repeatable, adds
  --remove-label TEXT          repeatable, removes
  --status [new|todo|in-progress|on-hold|done|cancelled]   must be allowed in the current phase
  --source-type [git|local]    closed tasks only
  --source-path PATH           closed tasks only
  --priority [low|medium|high|critical|none]
  --due DATE|none
  --assignee TEXT|none         refused if another assignee is set, unless -f
  --dep, --depends-on REF      repeatable, adds
  --remove-dep REF             repeatable, removes
  -f, --force                  skip confirmations (`done` with unchecked criteria or
                               unsatisfied dependencies, reassigning)

chreos task open NAME [OPTIONS]            prints the work/ path on stdout (status on stderr)
  -P, --project TEXT
  --status [todo|on-hold|in-progress|done|cancelled]   default: todo or on-hold, from dependencies
  --assignee TEXT              assign while opening (same rule as update)
  --recreate                   remove and recreate work/ even if it exists
  --base REF                   git: starting point for a new branch
                               (default: origin/HEAD if set, else HEAD)
  -f, --force                  skip confirmations (work/ cleanup on --recreate, `done`, reassigning)

chreos task close NAME [OPTIONS]
  -P, --project TEXT
  --status [done|cancelled]    set before closing
  -f, --force                  skip confirmations (cleanup, `done`)

chreos task archive NAME [OPTIONS]                closed tasks; see §7
  -P, --project TEXT
  --status [done|cancelled]    with -f on an open task: set before closing
  -f, --force                  close an open task first, skipping its confirmations

chreos task restore NAME [-P PROJECT]
chreos task delete NAME [-P PROJECT] [-f|--force]
chreos task rename NAME NEW_NAME [-P PROJECT]     see §7
chreos task move NAME PROJECT [-P PROJECT]        closed or archived tasks; see §7

chreos task list [OPTIONS]
  -P, --project TEXT           default: config's default project
  --all-projects
  -l, --label TEXT             repeatable, AND
  -n, --name TEXT
  -t, --title TEXT
  -s, --summary TEXT
  -S, --search TEXT
  --phase [open|closed]        repeatable, OR
  --status [...]               repeatable, OR; default hides done and cancelled
  --all                        include every status
  --ready                      only ready tasks (§6)
  --depends-on REF             only tasks that depend on REF
  --priority [low|medium|high|critical]   repeatable, OR
  --due-before DATE            due strictly before DATE
  --overdue                    due before today and not done or cancelled
  --assignee TEXT              repeatable, OR
  --unassigned                 only tasks without an assignee
  --archived                   list archived tasks (.archive/) instead of live ones
  --sort [name|created|updated|status|priority|due]   default: name;
                               priority sorts critical first, due sorts earliest first,
                               unset values last
  --json

chreos task show NAME [-P PROJECT] [--json]        includes dependency statuses and dependents
                               (text: the file, then a Dependencies and a Dependents block)
chreos task edit NAME [-P PROJECT]
chreos task path NAME [-P PROJECT] [--work]        --work: the work/ folder (open tasks only)

chreos task description|ac|refs|notes ...     see §9
```

Examples:

```
chreos task create redesign-homepage -P website-relaunch -t "Redesign homepage" \
    --source-type git --source-path website -l urgent
chreos task create launch -P website-relaunch --dep task:redesign-homepage --dep decision:hosting-provider
chreos task update redesign-homepage -P website-relaunch --priority high --due 2026-10-15
chreos task list --all-projects --ready --unassigned --sort priority
chreos task open website-relaunch/redesign-homepage --assignee claude
cd "$(chreos task path website-relaunch/redesign-homepage --work)"
chreos task open website-relaunch/redesign-homepage --status in-progress
chreos task open website-relaunch/redesign-homepage --recreate -f
chreos task close website-relaunch/redesign-homepage --status done
chreos task update default/old-idea --status cancelled
chreos task list --all-projects --phase open --json
chreos task archive website-relaunch/old-newsletter-signup
chreos task archive website-relaunch/spike-cdn -f --status cancelled
chreos task move default/build-cli internal-tooling
chreos task delete website-relaunch/migrate-cms -f
chreos task rename website-relaunch/migrate-cms migrate-content
chreos task list --all-projects --overdue --json
```

### 12.4 `chreos decision`

```
chreos decision create NAME [OPTIONS]
  -P, --project TEXT           default: config's default project
  -t, --title TEXT             default: NAME
  -s, --summary TEXT
  -l, --label TEXT             repeatable; comma-separated values also accepted
  --dep, --depends-on REF      repeatable; task:… or decision:…
  --status [pending|decided]   default: pending
  -f, --force                  skip the confirmation for `decided` with unsatisfied dependencies

chreos decision update NAME [OPTIONS]
  -P, --project TEXT
  -t, --title TEXT
  -s, --summary TEXT
  -l, --label TEXT             repeatable, adds
  --remove-label TEXT          repeatable, removes
  --status [pending|decided]
  --dep, --depends-on REF      repeatable, adds
  --remove-dep REF             repeatable, removes
  -f, --force                  skip the confirmation for `decided` with unsatisfied dependencies

chreos decision delete NAME [-P PROJECT] [-f|--force]
chreos decision rename NAME NEW_NAME [-P PROJECT]     see §7
chreos decision move NAME PROJECT [-P PROJECT]        see §7

chreos decision list [OPTIONS]
  -P, --project TEXT           default: config's default project
  --all-projects
  -l, --label TEXT             repeatable, AND
  -n, --name TEXT
  -t, --title TEXT
  -s, --summary TEXT
  -S, --search TEXT
  --status [pending|decided]   repeatable, OR; default: pending only
  --all                        include every status
  --depends-on REF             only decisions that depend on REF
  --sort [name|created|updated|status]   default: name
  --json

chreos decision show NAME [-P PROJECT] [--json]    includes dependency statuses and dependents
chreos decision edit NAME [-P PROJECT]
chreos decision path NAME [-P PROJECT]

chreos decision description ...     see §9
```

Examples:

```
chreos decision create hosting-provider -P website-relaunch -t "Hosting provider" --dep decision:frontend-framework
chreos decision update website-relaunch/hosting-provider --status decided
chreos decision list --all-projects --json
chreos decision delete website-relaunch/old-idea -f
chreos decision move default/ci-provider internal-tooling
$EDITOR "$(chreos decision path website-relaunch/hosting-provider)"
```

## 13. Configuration

```
~/.scepsis/
├── config.toml
└── templates/          # optional template overrides
```

```toml
[workspace]
path = "/home/user/scepsis-workspace"

[defaults]
project = "default"

[source]
git_path = "~/code"      # base folder for relative git sources
local_path = "~/files"   # base folder for relative local sources

[output]
format = "text"   # "text" | "json"; --json overrides per invocation
```

| Key | Type | Required | Notes |
| --- | --- | --- | --- |
| `workspace.path` | path | yes | Root of the workspace; project folders live directly under it. |
| `defaults.project` | string | yes | Must name an existing project; `init` creates it. |
| `source.git_path` | path | no | Base folder that relative `git` task sources are resolved against (§11.2). |
| `source.local_path` | path | no | Base folder that relative `local` task sources are resolved against (§11.2). |
| `output.format` | enum | no | `text` if absent. |

**Path rule** (config values and CLI options alike): a path is either absolute or is `~` or starts with `~/` (expanded to the user's home; `~user` forms are not accepted). The only relative paths accepted anywhere are task `source.path` values, which are resolved against `source.git_path` or `source.local_path`.

`~/.scepsis/templates/` may hold template overrides (§8).

`config.toml` is shared by the whole Scepsis framework: future `chreos` command sets will add their own tables to it.

`chreos init` creates `~/.scepsis/config.toml`, the workspace directory, and the default project. If a config already exists, it asks before overwriting it (`-f` skips the question; without a terminal and without `-f`, it fails). Overwriting writes a fresh file from the given options; existing projects in the workspace are left untouched, and the default project is created only if missing. `init` doesn't create the source base folders (they are the user's own folders); it warns when one doesn't exist. The TOML file is documented and hand-editable; `config get` prints one value and `config set` changes one (only the keys in the table above; other tables belong to other command sets and are preserved), validating it against the table above (e.g. `defaults.project` must name an existing project). `config set` rewrites the file atomically, preserving comments and key order (implementation: `tomlkit`); `none` removes an optional key.

## 14. Out of scope

These are not planned, now or later:

- Keeping the workspace itself under version control for history or auditing. Users may still do it themselves.
- Branch helpers (deleting or merging a task's branch after closing) and pushing branches.
- Version control systems other than git.
- Automatic status changes, automatic archiving, and pruning archived tasks.
- Archiving decisions or projects.
- A project overview (task and decision counts by status) in `project show`.
- Superseded decisions (marking a decision as replaced by another).
- Recurring tasks and bulk operations.
