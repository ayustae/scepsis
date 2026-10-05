# Scepsis - tools/AGENTS.md

## Description

- Read the local `README.md` for more information.

## Rules and conventions

- Each tool goes into its own folder.
- Use a Test Driven Development (TDD) approach
  1. Write a test that expresses the contract and run it — it must fail.
  2. Write the minimum implementation to make it pass.
  3. Refactor as required. Tests must still pass.
- Write tests for every function or behaviour you implement.
- Prefer small, focused changes over large rewrites.
- All the input ingested by the tool must be sanitized and validated.
- Do not add unnecessary dependencies. Always weigh the cost of adding a full dependency or library against the actual benefits it brings.
- Always pin the versions of all used dependencies.
- Each tool has a `README.md` with, at least, the following information:
```markdown
# Scepsis - <tool-name>

Short tool description in one or two lines at most.

## Build instructions (optional)

## Test instructions

Test instructions go here.

## Installation instructions

Standalone installation instructions go here

## Versions and dependencies

| **Component** | **Version** |
| --- | --- |
| **Language** | `Semantic version` |
| **Dependency 1** | `Semantic version` |
```
- Each tool has an `AGENTS.md` if, and only if, additional context information is needed with the following format:
```markdown
# Scepsis - tools/<tool-name>/AGENTS.md

## Description

- Read the local `README.md` for more information.

## ...
```
- Information meant for users and agents go in the `README.md`. Information meant for AI agents goes into the `AGENTS.md`
