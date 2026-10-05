# Defining, routing and tracking tasks

This skill produces **a task written down and routed, not executed**. It works
the same for technical work and for work that is not. It also drives a task
through its life when the user asks to work on it: opening it, recording
progress, verifying and closing it.

State lives in the **chreos workspace**: projects, each holding tasks and
decisions. Work with it **only through the `chreos` CLI**; do not look for its
files on disk. For every command and option, use `chreos --help` and
`chreos COMMAND [SUBCOMMAND] --help`.

## Ground rules

- **Everything goes through `chreos`**: frontmatter (status, labels,
  dependencies, priority…) and the sections it has commands for (a task's
  `description`, `ac`, `refs` and `notes`; a decision's `description`). It keeps
  names, timestamps and references consistent. Do not use the `edit` commands
  (they open an editor and need a terminal), and do not edit the files on disk.
- **Read with `--json`**: `list` and `show` output is a stable contract.
- **Look before writing**, so you neither duplicate nor contradict:

  ```sh
  chreos project list
  chreos task list --all-projects --json
  chreos decision list --all-projects --json
  ```

- **Show before writing.** Every create or change is proposed to the user as the
  exact commands (including the text they write) and run **only after they
  approve it**.
- **Confirmations.** Some commands ask first (deleting, losing files in a task
  folder, a task becoming `done` with unchecked criteria or unsatisfied
  dependencies, reassigning). Without a terminal they fail instead of asking.
  When that happens, tell the user what the prompt was about and pass `-f` only
  after they explicitly agree.
- If `chreos` is not installed or not initialised, tell the user and stop. Do
  not improvise a task list somewhere else.

## Step 1 — Separate tasks from decisions

**If the goal starts with "decide", "assess", "choose" or "approve", it is not a
task.** It is a decision for the user, and executing on an open decision is the
most expensive way to waste time.

```sh
chreos decision create hosting-provider -P website-relaunch \
  -t "Hosting provider" -s "Where the relaunched site will be hosted."
```

Put the gist of the question in the summary (`-s`), and the rest in the
decision's description, in `###` subsections:

```sh
chreos decision description replace website-relaunch/hosting-provider <<'EOF'
### Context

Why this has to be decided now, and what is already known.

### Options

- **Provider A**: wins …, loses …
- **Provider B**: wins …, loses …

### Recommendation

Provider B, because …

### Consequences

Unblocks `task:deploy-site`. While open, …
EOF
```

- **Context and options**: the problem, the real options with what each one
  wins and loses.
- **Recommendation**: always explicit. Without one the decision is useless.
- **Consequences**: what it unblocks and what happens while it stays open.
- **Decision**: absent until the user decides. When they do, add the option
  chosen **and why** — without the why it gets re-argued in three months:

  ```sh
  chreos decision description append website-relaunch/hosting-provider <<'EOF'
  ### Decision

  Provider B (decided by the user on 2026-10-05): …
  EOF
  chreos decision update website-relaunch/hosting-provider --status decided
  ```

The description may not contain `#` or `##` heading lines; use `###` and deeper.

Work that cannot start until the decision is taken depends on it:
`--dep decision:hosting-provider`. Tasks then stay `on-hold` when opened, and
`chreos task list --ready` leaves them out until the decision is `decided`.

What can be a task is *gathering the missing fact* needed to decide.

## Step 2 — Define

A task is not defined until it has all three. If one is missing, **ask**; do not
fill it in out of inertia.

| Part | Where it goes | Bad / good |
| --- | --- | --- |
| **Observable goal** | the title (`-t`), with a one-line summary (`-s`) | ❌ "improve performance" · ✅ "the home page loads in under 1 s on 4G" |
| **Acceptance criteria** | `chreos task ac append NAME -a "…"`, one per criterion | ❌ "that it works" · ✅ "all 4 options compared on cost, limits and a verdict" |
| **Context** | `chreos task description replace NAME` | why it exists, what is already known, what was ruled out |

Rule of thumb: **if you cannot say what will be written or changed when it is
finished, the task is not defined** (or it is a decision in disguise).

The task name is a short slug the user will recognise (`redesign-homepage`): it
is also the name of the git branch if the work happens in a repository.

## Step 3 — Break it down

Cut it up until each piece fits in one session. chreos has **no task
hierarchy**: pieces are sibling tasks in the same project, and order is
expressed with dependencies. When the whole needs tracking, a final task (e.g.
"launch") depends on its pieces.

```sh
chreos task create build-api -P website-relaunch --dep task:define-schema
chreos task create launch    -P website-relaunch --dep task:build-api --dep task:redesign-homepage
```

Two pieces with no dependency between them can be worked at the same time, even
by different subagents. Do not over-slice: eight five-minute tasks are worse
than two twenty-minute ones, because every hop costs context.

## Step 4 — Classify: who executes each piece

The question is not "which is more powerful?" but **"does the intermediate
output need to be seen?"**. The executor is stored as labels.

| Executor | When | Labels |
| --- | --- | --- |
| **Subagent** | It produces a lot of output nobody will re-read, and the result boils down to little | `executor=subagent`, `agent=<name>` |
| **Main thread** | The user's judgement is needed turn by turn | `executor=main-thread` |
| **Skill** | A repeatable procedure you want to watch run | `executor=skill`, `skill=<name>` |
| **Hook** | It has to happen *always*, not depend on the agent remembering | `executor=hook` |
| **Script** | Deterministic, no judgement | `executor=script` |
| **User** | Only a person can do it | `executor=user` |

A subagent is the biggest context saving there is: its output stays in its own
window and only the conclusion comes back. But **do not send a subagent
something the user wants to watch**: it goes far before they can stop it, and
that cost beats the saving.

The executor says who *should* do it; `assignee` says who *is* doing it, and is
set when the task is opened (Step 6).

## Step 5 — Write it

Propose the full set of commands, then run them once approved:

```sh
chreos task create redesign-homepage -P website-relaunch \
  -t "Home page hero matches the brand refresh" \
  -s "New hero section and layout per the brand refresh." \
  -l executor=main-thread --priority high --due 2026-10-15 \
  --dep decision:frontend-framework \
  --source-type git --source-path website

chreos task description replace website-relaunch/redesign-homepage <<'EOF'
The current hero doesn't reflect the new brand. The design system already has a
hero pattern; reuse it rather than building a new one.
EOF

chreos task ac append website-relaunch/redesign-homepage \
  -a "Hero renders correctly at 320px and 1440px" -a "Lighthouse performance >= 90"

chreos task refs append website-relaunch/redesign-homepage \
  -r "[Hero pattern](https://design-system.example.com/hero-pattern)"
```

| Situation | Option |
| --- | --- |
| Another project than the default | `-P PROJECT`, or `PROJECT/NAME` |
| It depends on another task or a decision | `--dep task:NAME`, `--dep decision:NAME` (`task:PROJECT/NAME` across projects) |
| A link, a document or a related item | `chreos task refs append NAME -r …` |
| Where the work happens is known | `--source-type git` or `local`, with `--source-path PATH` (required to open it) |
| A deadline | `--due YYYY-MM-DD` |

When you are done, **show what you created** (`chreos task show NAME`) **and
stop**. Do not execute in the same breath: the value of this skill is in the
altitude, and if it executes without the user validating the definition,
nothing has been gained.

## Step 6 — Working on a task

Only when the user asks to start one.

1. Pick it: `chreos task list --all-projects --ready --sort priority --json`
   lists what can be worked on next.
2. Open it, assigning yourself (by your agent name, e.g. `claude`):

   ```sh
   chreos task open website-relaunch/redesign-homepage --assignee claude --status in-progress
   ```

   Opening needs a `source`; if it has none, ask the user where the work happens
   and set it with `chreos task update … --source-type … --source-path …`. For a
   git source, `open` creates a worktree on a branch named after the task.
3. Work in the folder printed by `chreos task path NAME --work`.
4. Record progress, findings and hand-off context as you go:
   `chreos task notes append NAME -N "…"`. Notes are what lets someone else (or
   you, in another session) pick the task up.
5. **Verify each acceptance criterion.** If your assistant has the
   `verification` agent, delegate to it: give it the task (`PROJECT/NAME`) and
   what you claim is done. It checks the real state and answers with a verdict
   per criterion, numbered as `chreos task ac show NAME` lists them. Without
   the agent, run the same two checks yourself: is it done (against the real
   state, not your summary), and is it what was asked. Record the evidence with
   `chreos task notes append NAME -N "Verified: <criterion> — <how>"`, then tick
   only the verified criteria: `chreos task ac check NAME 1 3`. Never use
   `chreos task ac replace` for this: it rewrites the list with every criterion
   unchecked.

## Step 7 — Closing

1. Verify the work against every acceptance criterion (Step 6, with the
   `verification` agent when available). Do not tick what was not checked. If
   the verdict is `DOES NOT MATCH` or `DONE BUT NOT WHAT WAS ASKED`, report it to
   the user and do not close the task.
2. Close it:

   ```sh
   chreos task close website-relaunch/redesign-homepage --status done
   ```

   If criteria are unchecked or dependencies unsatisfied, chreos asks — and,
   without a terminal, fails. That check **is** Scepsis's principle that work,
   especially an AI's, is verified before it is accepted. **Never pass `-f` to
   get past it** unless the user, told exactly what is unchecked, says so.
   Closing removes the `work/` folder; a git branch is kept with the committed
   work.
3. Tasks that depended on this one stay `on-hold` until someone updates them:
   find them with `chreos task list --all-projects --depends-on task:PROJECT/NAME`
   and propose moving them to `todo`.
4. Work that will not be done is closed with `--status cancelled`, not deleted.
   Archive (`chreos task archive`) or delete only when the user asks.

## Step 8 — On closing: what was learned that is worth keeping

After verification, go through three triggers. They are the only ones that
justify proposing something new:

1. **A multi-step flow worth repeating.** Something was solved with a sequence
   that will be needed again and is in no skill today.
2. **A dead end that a way out was found for.** Something failed, something else
   worked; next time there is no need to trip over it again.
3. **A correction from the user.** It was done one way, the user said it should
   be another. The most valuable one, and the least written down.

If one came up, **propose** — do not write — whatever fits:

| What was learned | Where it goes |
| --- | --- |
| A repeatable procedure, without the history | A new skill, or a section in an existing one |
| A fact about the company or the team, with source and date | A context note (the `context` skill) |
| Something that only matters for this task | The task notes, and nothing else |

The proposal is shown as a diff of the file it would change and **applied only
if the user approves it**: an agent does not change its own instructions without
someone reading them first. If no trigger came up, say so ("nothing to propose")
and close.

## Common mistakes

- Editing frontmatter or list sections by hand instead of through `chreos`.
- Inventing the acceptance criteria to avoid asking.
- Recording a decision as if it were work — it sits on the list forever.
- Executing right after defining, without the user validating the definition.
- Passing `-f` to get a task to `done` past unchecked criteria.
- Ticking criteria that were not verified.
- Over-slicing.
