# idion — Data Model and Command Surface

System design for `idion`, the Scepsis user context CLI (`tools/idion/`): the on-disk layout of context files, their format, how they are identified and listed for AI models, and the proposed command interface, with the reasoning behind each decision.

Status: implemented (`tools/idion/`). Command reference: `docs/cli/idion/`.

*Idion* (ἴδιον) is Greek for "what is one's own": the user's own context.

## 1. Guiding principle

Context files are Markdown files that tell AI models about the user: who they are, their team and neighbouring teams, company documentation grouped by project, and so on. Each file starts with a one-line `description`. An AI model loads **only the descriptions** of all context files (later, through a hook, skill or prompt; see §9) and opens a file only when it needs that piece of context. This keeps the context the AI loads up front small, however large the tree grows.

The files are meant to be opened and edited by **humans and AI agents alike**, with any editor or file tool. The CLI is a convenience layer: creating files, changing descriptions, appending to and replacing bodies, listing and showing. Consequently:

- The CLI never imposes a body structure; it changes a body only through `append`, `replace` and `edit` (§6).
- The CLI must tolerate hand edits: extra unknown frontmatter fields, reordered keys, YAML comments and arbitrary body content are all valid and are preserved byte-for-byte.
- A hand-broken file (invalid YAML, missing description) is reported, not fatal: commands keep working on every other file, and `idion check` lists every problem.

## 2. Storage layout

The context tree is a plain directory tree at the fixed path `~/.scepsis/context/`, created by `idion init` with mode `0700`: context files describe the user and may hold private details, so only the user can read them. `init` never changes an existing root. No database. The tree is **free-form**: the user decides the folders. An example:

```
~/.scepsis/context/
├── .idion.lock                       # write lock (§6), never a context file
├── user.md                           # the user: role, background, preferences
├── teams/
│   ├── _index.md                     # optional folder description
│   ├── my-team.md
│   └── data-platform.md
└── company/
    ├── _index.md
    └── projects/
        └── atlas/
            ├── _index.md
            ├── architecture.md
            └── runbooks.md
```

Rules:

- Every `*.md` file in the tree is a **context file**, except `_index.md`.
- `_index.md` is the optional **folder description** of the folder it sits in (§5). The root may not have one; its description is the tool's purpose.
- Names starting with `_` are reserved for the tool; `_index.md` is the only one used today.
- Entries starting with `.` are ignored (e.g. `.idion.lock`, a `.git/` folder if the user versions the tree).
- Other files (non-`.md`) are ignored by commands and reported by `check` as warnings.
- Symbolic links are not followed; `check` reports them as warnings. This keeps every path the CLI touches inside the root.

**Why a fixed path:** the context belongs with the rest of the user's framework data in `~/.scepsis/`, and a fixed path lets hooks and skills find it without reading a configuration. Unlike the chreos workspace, there is no reason to place it elsewhere.

**Why free-form folders:** what context a user needs differs from user to user. Imposing categories (teams, projects, …) would fit nobody exactly; the folder descriptions (§5) give the AI the same guidance a fixed scheme would.

## 3. File format

```markdown
---
description: Members, responsibilities and rituals of my team (Data Platform).
---

# My team

Free Markdown content.
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `description` | string | yes | A short summary of the contents, telling the AI when to open the file. Non-empty, a single line, at most 200 characters, leading and trailing whitespace stripped. |

- Unknown fields are allowed and preserved (users may keep their own metadata).
- The body is free. The CLI never restructures it.
- `_index.md` has the same format; its `description` summarizes the folder's contents, and its body (usually empty) is free.
- The description is validated, not rewritten: an invalid value is rejected with an explanatory error.

**Why a single field:** the description is the only thing the AI needs in order to decide whether to open a file. Titles, timestamps or tags would grow the list the AI loads without helping that decision; the body's H1 can hold a title for humans.

## 4. Identifiers

A context file is identified by its path relative to the root, without the `.md` extension: `user`, `teams/my-team`, `company/projects/atlas/architecture`. A folder is identified by its relative path with a trailing `/`: `teams/`, `company/projects/atlas/`. The root is `/`.

- Each path segment follows the chreos name pattern `^[a-z0-9]+(-[a-z0-9]+)*$`, at most 64 characters (chreos design §5).
- At most 8 segments.
- Identifiers are **validated, not sanitized**: an absolute path, `.` or `..` segments, empty segments, a trailing `.md`, a reserved `_` name or an invalid segment is rejected with an explanatory error, never silently rewritten. After validation the resolved path is checked again to lie inside the root.
- A folder identifier must end with `/`: the CLI never guesses whether `teams` means the file `teams.md` or the folder `teams/`. A command that expects one kind and gets the other fails with a hint (`did you mean 'teams/'?`).
- No entry below the root may be a symbolic link; a path through one is rejected. The root itself may be a symbolic link (e.g. to a synced folder).
- A file and a folder may share a name (`atlas.md` next to `atlas/`): the trailing `/` tells them apart. `check` warns about it, since it's usually a mistake.

**Why paths as identifiers:** the identifier is where the file is. Humans and agents can open the file directly from a listing, and there is no second naming scheme to keep in sync.

## 5. Listing and collapsing

`list` prints one line per entry, `<identifier> — <description>`, sorted by identifier:

```
company/projects/atlas/architecture — Atlas service architecture and dependencies.
company/projects/atlas/runbooks — Links to the Atlas on-call runbooks.
teams/data-platform — The Data Platform team: scope, contacts, channels.
teams/my-team — Members, responsibilities and rituals of my team.
user — The user: role, background, working preferences.
```

`--depth N` **collapses** everything deeper than `N` segments into its folder at depth `N`, shown with the folder's description and how many context files it holds:

```
$ idion list --depth 1
company/ — Company documentation references, grouped by project. (2 files)
teams/ — My team and the other teams in the department. (2 files)
user — The user: role, background, working preferences.
```

- A collapsed folder without `_index.md` is shown as `<identifier> — (no description) (N files)`; `check` warns about it. A file whose description is missing or invalid is shown as `<identifier> — (invalid description)`.
- `list PREFIX` limits the listing to a folder (`list teams/`), which must exist; depth then counts from that folder. Identifiers are always printed in full, from the root, so they can be passed to `show` as they are. The prefix folder itself is not listed, just as the root isn't.
- `--depth` is at least 1. Without it, every file is listed.
- `--folders` also lists described folders that aren't collapsed (without a file count). Undescribed folders and folders without context files are never listed on their own.
- `-S TEXT` keeps only files whose identifier or description contains `TEXT` (any case). It applies **before** collapsing: collapsed folders count matching files only, and folders without matches disappear.
- If the scan finds problems under the prefix, `list` prints a single `warning: N problems in the context tree; run 'idion check'` line on stderr and still exits `0`; stdout carries only the listing, so hooks can use it as is.
- This listing (text or `--json`) is what the future hook or skill loads into the AI's context (§9). Collapsing lets a large tree start as a short list that the AI expands with `idion list <folder>/` when it needs to.

`search TEXT [PREFIX]` complements `list -S`: it also matches bodies, and prints each matching body line with its line number in the file, so an AI can tell where a fact already lives before adding it, without opening every candidate file. It is a plain scan, no index.

**Why folder descriptions:** without them, the up-front listing grows with every file. With them, the user chooses how much detail the AI sees first.

## 6. CLI interface

This is the interface as designed, not user reference documentation (see `docs/cli/idion/`).

Conventions, the same as chreos's (chreos design §12):

- Every command accepts `-h/--help`; the root accepts `-V/--version`.
- `list`, `show` and `check` accept `--json`. The JSON output is a stable contract for scripts and agents:
  - `list` returns an array of objects `{"id", "kind": "file" | "folder", "description", "path"}` plus `"files"` (count) for collapsed folders; `description` is `null` for undescribed folders.
  - `show` returns `{"id", "path", "frontmatter", "body", "problems"}`. `problems` lists what is wrong with the file (empty when valid). When the frontmatter can't be parsed, `frontmatter` is `null` and `body` is the whole file text.
- `-f/--force` skips confirmations. A command that needs confirmation and runs without a terminal fails instead of waiting for input, unless `-f` is given. `edit` fails without a terminal.
- **Write lock:** every command that writes holds an exclusive OS file lock (POSIX `flock`) on `<root>/.idion.lock` for its whole duration; a second writer waits up to 10 seconds, then fails. Read-only commands don't lock.
- Exit codes: `0` success; `1` user or validation error; `2` usage error (Click's default).
- Body text options (`-b`, `-t`) accept `-` to read from standard input, so agents can pass multi-line text safely.

```
idion [-h|--help] [-V|--version]

idion init                              create ~/.scepsis/context/ (no-op if it exists)

idion create ID -d DESC [OPTIONS]       create a context file; missing parent folders are created
  -b, --body TEXT                       initial body ('-' reads stdin); default: '# <last segment>'
  --body-file PATH                      initial body from a file

idion show ID [--json]                  print the file (frontmatter and body)

idion list [PREFIX] [OPTIONS]           list identifiers and descriptions (§5)
  --depth N                             collapse below N segments
  --folders                             also list described folders
  -S, --search TEXT                     case-insensitive substring match on id and description
  --json

idion search TEXT [PREFIX] [--json]     files whose id, description or body contains TEXT,
                                        with the matching body lines and their line numbers

idion update ID -d DESC                 change a file's description
idion append ID -t TEXT                 append a paragraph to a file's body ('-' reads stdin)
idion replace ID -b TEXT                replace a file's body ('-' reads stdin)
  --body-file PATH                      the new body from a file (instead of -b)
idion edit ID                           open in $VISUAL/$EDITOR, validate afterwards (FOLDER/: its _index.md)

idion folder describe FOLDER -d DESC    create or update FOLDER/_index.md; creates the folder if missing
idion folder show FOLDER [--json]       print FOLDER/_index.md

idion check [--json]                    validate the whole tree (§7)

idion move SRC DST                      move a file to a file, or a folder/ to a folder/
idion delete ID [-f]                    delete a file, or a folder/ with everything in it
```

`create` validates the identifier, the description and the body before writing anything, fails if the file exists, creates missing parent folders and prints the new file's absolute path on stdout (so agents can open it directly). `-b` and `--body-file` exclude each other; without either, the body is `# <last segment>`. The body is free text, except that it may not contain NUL characters.

`show` prints the file exactly as it is on disk; problems with it (broken frontmatter, invalid description) are printed as warnings on stderr and don't change the exit code, so a broken file can still be read and fixed.

`folder describe` refuses the root (it has no description) and folder identifiers without the trailing `/`. It creates missing folders; a new `_index.md` gets only the frontmatter (empty body), while an existing one is changed like `update` changes a file. It prints the `_index.md` path. `folder show` prints the `_index.md` like `show` prints a file (same text and JSON output, with `id` set to the folder identifier, e.g. `teams/`); a missing folder or a folder without `_index.md` is an error with a hint to use `folder describe`. An `_index.md` that is a symbolic link is refused.

`edit` follows the chreos edit flow (chreos design §12): unchanged file → its existing problems are reported as warnings, exit `0`; changed and valid → exit `0`; changed but the frontmatter doesn't parse → the file is left exactly as saved, with a hint to run `edit` again, exit `1`; changed with an invalid description → the errors are reported, exit `1`. The CLI never writes, reverts or "fixes" the edited file: idion has no field to bump, so unlike chreos `edit` doesn't write or lock at all. `edit` also accepts a folder identifier (`idion edit teams/`) and then opens the folder's `_index.md`, so a broken folder description can be fixed the same way. Without a terminal it fails with a hint naming the commands that make the same changes without an editor (`replace` and `update`, or `folder describe` for a folder) and the file's path.

`update`, `append`, `replace` and `folder describe` rewrite only what they change (non-destructive frontmatter round-trip, atomic write). A trailing YAML comment on a changed line is kept, though the spaces before it may be realigned. They refuse a file whose frontmatter can't be parsed, with a hint to fix it with `idion edit` or by hand: the CLI never rewrites a file it can't round-trip.

- `update` changes only `description`, and also repairs a missing or invalid one. An unchanged value isn't rewritten.
- `append` trims the body's trailing line breaks, then adds a blank line, the text and a final line break (an empty body becomes `\n<text>\n`, the layout `create` uses). Line breaks in the text are converted to the file's own, so CRLF files stay CRLF. Blank text is refused. A file with an invalid description can still be appended to; the problem is printed as a warning.
- `replace` sets the whole body, leaving the frontmatter alone. It takes the body like `create` (`-b TEXT`, `-b -` or `--body-file`; exactly one), lays it out the same way (a blank line after the frontmatter, a final line break; empty text clears the body) and converts line breaks to the file's own. An unchanged body isn't rewritten; an invalid description is a warning, as for `append`. It exists so that agents, which can't use `edit` without a terminal, can reword or restructure a file.
- Like `create`, all three print the file's path.

`move SRC DST` moves a file to a file or a folder (with everything in it) to a folder, in one atomic rename; it never overwrites, never moves the root or a folder into itself, creates missing parents and leaves emptied folders in place. `delete ID [-f]` deletes a file, or a folder with everything in it. It asks first (`-f` says yes; without a terminal and without `-f` it fails, as in chreos), and a folder holding anything besides its `_index.md` additionally requires `-f`, so a whole subtree is never deleted by just answering a prompt.

## 7. Validation (`check`)

`check` walks the whole tree and reports:

- **Errors:** unparseable frontmatter, a missing or invalid `description`, an entry whose name isn't a valid identifier segment, an `_index.md` in the root, a folder nested deeper than 8 levels, an unreadable folder. Entries with an invalid name or nested too deeply are skipped with their whole subtree.
- **Warnings:** folders with context files but no `_index.md`, non-`.md` files, symbolic links, empty folders, a file and a folder with the same name.

Findings are sorted errors first, then by path. The text output is a table (severity, path relative to the root, identifier or `-`, message) followed by `N errors, M warnings`; a clean tree prints `no problems found`. It exits `1` if there is any error, `0` otherwise (warnings alone don't fail). The JSON output is `{"findings": [{"severity", "path", "id", "message"}], "errors": N, "warnings": M}`, with absolute paths, as in chreos. `check` only reads: unlike chreos it has no `--fix`, since there are no caches to repair.

## 8. Implementation notes

- Package `tools/idion/`, Python, same stack and versions as chreos: uv (`uv_build`), Click, ruamel.yaml, pytest. No `tomlkit` until a configuration is needed.
- `idion` is standalone and doesn't depend on chreos. The few modules it needs are copied from chreos and adapted:
  - `frontmatter.py`: non-destructive frontmatter round-trip, without chreos's representers for timestamps, enums and `null` (idion only writes strings);
  - `fileio.py`: atomic writes;
  - `lock.py`: the write lock;
  - `output.py`: the text/JSON output pattern.
- No `~/.scepsis/config.toml` keys in v1: the root is fixed and `--json` is chosen per invocation. If a configuration is needed later, idion adds its own `[idion]` table to the shared file (chreos design §13).
- Supported platforms: Linux and macOS (the lock uses POSIX file locks), as for chreos.

## 9. AI integration (later)

Not part of the CLI design, recorded here so the CLI serves it: a hook, skill or prompt runs `idion list --depth N` at the start of a session and puts the output in the AI's context, together with a short instruction on how to read (`idion show` or the file itself) and expand (`idion list <folder>/`) entries. The skill will also tell the AI when and how to record new context with `create`, `append` and `update`. This is designed separately, once the CLI exists.

## 10. Out of scope

Not planned for v1:

- Hooks, skills and prompts (§9); designed separately.
- Search indexes, embeddings or any search beyond the case-insensitive substring match of `list -S` and `search`.
- Versioning or syncing the tree. Users may keep it under git themselves (`.git/` is ignored, §2).
- Templates for context files.
- Several context roots, or per-project context trees.
