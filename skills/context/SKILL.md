# User context

Keep what will be useful **three months from now and in another workspace**:
who the user is, their team and the teams around them, reference documentation,
how things are run, and the decisions that are not tied to a single project.

The store is the user's **context tree**: Markdown context files grouped in
free-form folders that the user organises as they like. Work with it **only
through the `idion` CLI**; do not look for its files on disk. For every command
and option, use `idion --help` and `idion COMMAND --help`.

Each context file has an **identifier**, such as `teams/my-team`; a folder's
identifier ends in `/`, such as `teams/`. Each file also has a `description`
field in its frontmatter. `idion` sets it with `-d` when you create or update the
file, and folders get theirs with `idion folder describe`. `idion list` prints
each file as `<identifier> — <description>`:

```
$ idion list --depth 2
company/projects/ — Company documentation references, grouped by project. (3 files)
teams/my-team — My team: members, what each one owns, rituals and channels.
teams/other-team — Other team: members, what they own, how to reach them.
user — The user: role, background, working preferences.
```

**That listing is all an AI sees up front.** A file's body is read only when it
is needed, with `idion show ID`.

## Before anything

1. If the listing of the context tree is not already in your context, load it:

   ```sh
   idion list --depth 2
   ```

   Collapsed folders show as `teams/ — <description> (N files)`. Expand one with
   `idion list teams/` and read a file with `idion show teams/my-team`.
2. If `idion` is not installed, or it fails with `run 'idion init' first`, tell
   the user and stop. Do not improvise a store somewhere else.

## First rule: extend before creating

The risk with a store like this is that it ends up **hard to consult because it
is spread across too many files**. So:

1. **Search before writing anything.**

   ```sh
   idion search "<subject>"       # identifiers, descriptions and bodies, with matching lines
   idion show teams/other-team    # read the likely candidates in full
   ```

2. **By default, extend an existing file** with `idion append`. A new paragraph
   in `teams/other-team` beats a new file about something a teammate said.
3. **Create a new file only when nothing fits**: a new subject (another team,
   another area of documentation) that is also going to grow.
4. If a file becomes unmanageable, **propose** splitting it (or moving it with
   `idion move`) and linking the parts. Never reorganise by surprise.

When in doubt: extend. A long file gets read; five short ones do not get found.

## The description is the index

The description is all an AI sees before deciding to open a file, so it has to
be enough to make that decision.

- One line, at most 200 characters.
- Say **what is inside and when it is worth opening**: ❌ "Team notes" ·
  ✅ "Data Platform team: members, what each one owns, on-call rota and channels."
- When a file grows past what its description says, update it with
  `idion update ID -d "…"`.
- Every folder holding files gets a description with
  `idion folder describe FOLDER/ -d "…"`. Without one, `idion check` warns and
  the collapsed listing shows `(no description)`, which tells the AI nothing.

## What deserves a note and what does not

| Yes | No |
| --- | --- |
| The user's role and team, what the team does | What is already in a project's `AGENTS.md` or `README.md` |
| Other teams, who is in them and what they own | Details of a single task: they go in the task (the `task` skill) |
| How things run: rotas, escalation, boards, channels | Notes about a single person: they do not exist |
| Reference documents, and which ones are stale | Copies of documentation: link it and summarise |
| Decisions and **why** they were taken | Conclusions that expire in days |
| Who said something and when, as a source | What only matters in this conversation |

Rule of thumb: if three months from now, in another workspace, it would not
change anything you would do, it is not a note.

## People go inside their team, and only the professional part

**There are no files per person.** About someone, store their name, their team,
what they own and what to ask them about, in a member list inside the team's
file — and their name as the source of a fact.

Never write, here or anywhere else: language, nationality, character, whether
they reply or not, whether they are temporary, whether to be careful with them.
That is material you could not show on a shared screen, and this store is meant
to be read.

## Sources and dates

idion manages a single frontmatter field, `description`, on purpose. So the source
goes **in the body, next to the fact it backs**:

```markdown
- Escalate to the team manager if the SME does not answer within 30 minutes.
  (source: Jane Doe, 2026-10-05)
- The deployment runbook lives in the Atlas wiki space; the 2024 page is stale.
  (source: Atlas wiki, checked 2026-10-05)
```

The source is not decoration: a year from now it is the only thing that tells
whether a fact still holds or was said in passing. **Always with an absolute
date**, never "last month".

## How to work

1. **Search first** (see above). If something on the same subject exists, that
   is the file.
2. **Write the why, not just the what.** "Jane is the manager" is worth little;
   "she is the step above the SME: escalate to her if the SME does not answer in
   30 minutes" changes what you would do.
3. **Contradictions: ask.** If the new fact clashes with what is written, do not
   overwrite it silently — reality may have changed, or the old fact may still
   be right. Ask, and leave a record of the change with its source and date.
4. **Show before writing.** Propose the change first: the full content of a new
   file, or the paragraph to append (or a diff) for an existing one, plus any
   description change. Run the `idion` command **only after the user approves
   it**. The user has to be able to stop it before, not correct it after.
5. **Write through `idion`**, passing multi-line text on standard input:

   ```sh
   idion create teams/other-team -d "Other team: members, what they own, rota and channels." -b - <<'EOF'
   # Other team

   ...
   EOF

   idion append teams/other-team -t - <<'EOF'
   - Owns the ingestion pipelines since 2026-09. (source: Jane Doe, 2026-10-05)
   EOF

   idion update teams/other-team -d "…"
   idion folder describe teams/ -d "My team and the other teams in the department."
   ```

   `create` creates missing parent folders. Describe any new folder in the same
   proposal.

   To reword, remove or restructure a body, replace it whole. Start from the
   current body (`idion show ID`), and show the user the full new body before
   running:

   ```sh
   idion replace teams/other-team -b - <<'EOF'
   # Other team

   ...
   EOF
   ```

   `replace` leaves the description alone; change that with `idion update`. Do
   not use `idion edit`, which opens an editor and needs a terminal, and do not
   edit the files on disk.
6. **Validate after every write**: run `idion check` and fix the errors it
   reports before finishing.
7. **Deleting** (`idion delete`) and **moving** (`idion move`) only when the user
   asks for it. Without a terminal `delete` needs `-f`, so pass it only after the
   user has confirmed that exact deletion.

## When to offer without being asked

- The user says "remember this", "take note", "save this".
- A fact about the organisation comes up that will still matter in three months.
- When closing a task, the `task` skill finds a fact about the company or the
  team worth keeping (see its closing step). A repeatable procedure without
  history belongs in a skill instead; a fact with a source and a date belongs
  here.

Offer it; the user decides.

## Common mistakes

- Creating a file per loose fact: exactly what makes the store hard to consult.
- Creating a file for a person, or writing anything about them beyond their role
  in their team.
- Storing the state of a task, which expires in days.
- Writing the what without the why, which is the only part that changes
  decisions.
- A vague description ("notes", "misc") that does not say when to open the file.
- Relative dates, or facts without a source.
- Writing first and telling afterwards.
