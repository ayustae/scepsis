# Scepsis - AGENTS.md

## Description

- Read `README.md` for a general project description.
- Under `docs/` there is additional documentation about the project. In the 10 first lines of each file there is an abstract including the document scope and contents. Read the full file only as needed.
- Some directories have additional `AGENTS.md` files with additional context for their scope.

## Structure

| **Target** | **Description** |
| --- | --- |
| `AGENTS.md` | AI agent context (this file) |
| `README.md` | General project description |
| `docs/` | Project documentation |
| `skills/` | Default skill definitions for installing in the framework |
| `agents/` | Default agent definitions for installing in the framework |
| `tools/` | Default tool definitions available in the framework |
| `templates/` | Template definitions for the markdown files used in the framework |

## Rules and conventions

- Every file except for `AGENTS.md` is meant to be read by humans and agents alike.
- Always attempt one task at a time.
- Always plan before attempting a task. Use plan mode for this if available.
- Always ask the user for approval before executing the plan.
- Always update any necessary documentation file after doing any change.
- The README should stay brief and focused, as it serves as the project frontpage. Any deeper documentation goes into `docs/`.
