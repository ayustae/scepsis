"""The reference docs (docs/cli/idion/) document every command and option.

Each leaf command has its own heading, e.g. ### `idion create`, and
every option flag of that command appears (as a whole token) in its section.
"""

import re
from pathlib import Path

import click
import pytest

from idion.cli import main

REFERENCE = Path(__file__).resolve().parents[3] / "docs" / "cli" / "idion"
HEADING = re.compile(r"^#+ `(idion(?: [a-z-]+)*)`\s*$")
pytestmark = pytest.mark.skipif(not REFERENCE.is_dir(), reason="repository docs/ not available")


def leaf_commands(command, path=("idion",)):
    subcommands = getattr(command, "commands", {})
    if not subcommands or path == ("idion",):
        yield " ".join(path), command
    for name, sub in subcommands.items():
        yield from leaf_commands(sub, (*path, name))


@pytest.fixture(scope="module")
def sections() -> dict[str, str]:
    found: dict[str, str] = {}
    for file in sorted(REFERENCE.glob("*.md")):
        current = None
        for line in file.read_text(encoding="utf-8").splitlines():
            match = HEADING.match(line)
            if match:
                current = match.group(1)
                found[current] = ""
            elif line.startswith("#"):
                current = None
            elif current:
                found[current] += line + "\n"
    return found


def test_every_command_has_a_section(sections):
    missing = [path for path, _ in leaf_commands(main) if path not in sections]
    assert missing == []


def test_every_option_is_documented_in_its_section(sections):
    missing = []
    for path, command in leaf_commands(main):
        text = sections.get(path, "")
        for param in command.params:
            if isinstance(param, click.Option):
                for flag in param.opts:
                    if not re.search(rf"(?<![\w-]){re.escape(flag)}(?![\w-])", text):
                        missing.append(f"{path} {flag}")
    assert missing == []
