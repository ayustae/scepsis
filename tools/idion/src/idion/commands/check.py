"""`idion check` (design §7)."""

import click

from idion.cli_support import CONTEXT_SETTINGS, emit_json, require_root
from idion.output import check_report, sorted_findings, table
from idion.tree import ERROR, scan


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option("--json", "as_json", is_flag=True, help="Print a JSON object.")
def check(as_json):
    """Validate the whole context tree; exits 1 if any error is found."""
    root = require_root()
    findings = sorted_findings(scan(root).findings)
    errors = sum(1 for finding in findings if finding.severity == ERROR)
    if as_json:
        emit_json(check_report(findings))
    elif findings:
        rows = [(f.severity, str(f.path.relative_to(root)), f.id or "-", f.message) for f in findings]
        for line in table(rows):
            click.echo(line)
        click.echo(f"{_plural(errors, 'error')}, {_plural(len(findings) - errors, 'warning')}")
    else:
        click.echo("no problems found")
    if errors:
        raise SystemExit(1)
