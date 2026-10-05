# Scepsis - tools/chreos/AGENTS.md

## Description

- Read the local `README.md` for more information.
- Design: `docs/system-designs/chreos-data-model.md`. Reference: `docs/cli/chreos/` (keep it in sync with every command or option change; `tests/test_reference_docs.py` fails when a command or option is undocumented).

## Structure

- `src/chreos/`: package (src layout). `cli.py` holds the root Click group `main`; subcommands attach to it and inherit its `-h/--help` context settings.
- Core modules (no workspace knowledge):
  - `errors.py`: `ChreosError` (exit 1), `FormatError` (unparseable file).
  - `model.py`: enums (`Kind`, statuses, `Phase`, `Priority`, `SourceType`) and single-value validation (names, labels, due, assignee, `none` handling, phase/status rule).
  - `schema.py`: whole-frontmatter validation per item type, returning `Problem`s instead of raising.
  - `frontmatter.py`: `parse`/`dump`/`load`/`save` of `Document(meta, body)`; ruamel.yaml round-trip, body kept byte-for-byte. Always go through it to write items.
  - `fileio.py`: `atomic_write`. `paths.py`: path rule and `scepsis_home()`. `timestamps.py`: `now()`.
  - `items.py`: tolerant loading (`load_items` turns broken files into failures).
  - `templates.py` + `templates/`: rendering new items; `templates/*.md` are copies of the repository `templates/` (kept identical by a test).
  - `body.py`: H1/summary sync on title/summary changes.
  - `markdown.py`: fenced-code-aware line scanning (`unfenced`, `has_unclosed_fence`) and newline detection; use it for any body parsing.
  - `sections.py`: locate/read/write one `## <heading>` section (§9), missing-section placement, description validation.
  - `lists.py`: list-item reading/appending/replacing within a section (acceptance criteria, references, notes).
  - `inputs.py`: TEXT argument or stdin (refuses to wait on a terminal).
- Workspace modules:
  - `workspace.py`: `Workspace(root)`: layout paths (names validated before use), discovery, uniqueness, `parse_item_name`, `resolve(ref)`.
  - `lock.py`: `workspace_lock(root)`; every writing command must hold it.
  - `refs.py`: `ItemRef`/`parse_ref` (prefixed item references), `classify_reference`/`validate_reference` for `## References`.
  - `graph.py`: `Graph.load(workspace)`: satisfaction, dependency statuses, dependents, ready tasks, `check_new_dependencies` (resolution + cycle refusal), `find_cycles`. Node identity comes from paths, not frontmatter caches.
- Lifecycle modules:
  - `git.py`: git via argument lists only (never a shell); every call checks git >= 2.30. Don't parse git's human-readable messages (they are localized).
  - `sources.py`: task sources; relative paths resolve against `bases` (from the config).
  - `confirmations.py`: `done`/`decided` messages and `require(message, confirm)`.
  - `lifecycle.py`: `open_task`, `close_task`, `cleanup`, `losses`. Validate and confirm before changing anything; save TASK.md last.
- Config and commands:
  - `config.py`: `load_config()` → typed `Config` (workspace, default project, source `bases`, output format); `get_value`/`set_value` for known keys only; `render_new_config` for `init`.
  - `projects.py`: `create_project`.
  - `cli_support.py`: `ChreosGroup` (ChreosError/OSError → exit 1), `confirmer(force)`, `warn`, `wants_json`/`emit_json`, `CONTEXT_SETTINGS`.
  - Item-command layer (shared by project/task/decision): `itemfields.py` (title/summary/labels/status updates with H1 sync), `listing.py` (filters, sorting), `output.py` (JSON shapes: a stable contract, change deliberately), `editing.py` (`edit` flow and `file_checks`), `commands/common.py` (context, `resolve` for NAME/`-P`, `PROJECT_OPTION`, list/show/edit helpers, `emit_dependency_show`, `modify_body`).
  - `tasks.py`: task rules for create/update (sources, priority/due/assignee, dependencies, confirmations), `set_assignee`, `task_checks` for `edit`, `task_predicate` for the task-only list filters. NAME/`-P` resolution is `Workspace.resolve_item_name` (commands use `commands/common.resolve`).
  - `dependencies.py`: dependency add/remove (by target) and `edit` checks, shared by tasks and decisions. `decisions.py`: decision create/update rules.
  - `check.py`: `check_workspace` (layout, files, uniqueness, archive state, dependencies, lifecycle, references → `Finding`s with error/warning severity) and `fix_caches`.
  - `commands/`: one module per command group (`setup.py`: `init`, `config`; `project.py`, `task.py`, `decision.py`, `check.py`), registered in `cli.py`. Commands stay thin: parse options, take the lock, call core functions, print.
- Workspace operations:
  - `relink.py`: `snapshot` before an operation, `rewrite(workspace, snapshot, node_map)` after it (one rule for rename/move/delete: resolve each reference with the holder's old project, map, write relative to its new project), `referrers` for confirmation messages.
  - `operations.py`: archive/restore, rename, delete, move for tasks, decisions and projects. Validate and confirm first, then change files, then `rewrite`.
- Conventions: core never prompts; it takes a `confirm(message) -> bool` callback (`-f` → always yes). Writers assume the caller holds `workspace_lock`.
- `tests/`: pytest suite, one file per module; command tests are `test_cmd_<group>.py`, run through `CliRunner` with `HOME` redirected and `cli_support.is_interactive` patched. Git tests use the `git_env` fixture (isolates the user's git config) via `git_repo`/`cloned_repo`; `yes`/`no` record confirmation messages. `tests/test_e2e.py` drives one workspace through every command group via the CLI; extend it when adding commands. The `ws` fixture (`tests/conftest.py`) builds real workspaces: `ws.project()`, `ws.task()`, `ws.decision()`, `ws.write()` for hand-made or broken files. Run commands with `conftest.run_cli(...)` (Click's `CliRunner`, `prog_name="chreos"`); `cli_home` gives an initialized workspace at `~/ws`. `result.output` mixes stdout and stderr: assert on `result.stdout`/`result.stderr`.

## Key commands

Run from `tools/chreos/`:

- `uv sync`: install pinned dependencies into `.venv`.
- `uv run pytest`: run the test suite.
- `uv run chreos ...`: run the CLI from source.
- `uv lock`: refresh `uv.lock` after changing pins in `pyproject.toml` (pins are exact; bump them deliberately and update the README versions table).
- `uv build`: build the wheel and sdist.
- `uvx pyflakes src/ tests/`: catch unused imports and names.

## Notes

- Click exits with `2` when `chreos` runs without a subcommand (help is printed); this matches the usage-error exit code in the design (§12).
