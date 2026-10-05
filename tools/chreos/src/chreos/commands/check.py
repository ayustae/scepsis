"""`chreos check` (design §12.1)."""

import click

from chreos.check import ERROR, check_workspace, fix_caches
from chreos.cli_support import CONTEXT_SETTINGS, emit_json, wants_json
from chreos.commands.common import JSON_OPTION, load_context
from chreos.lock import workspace_lock
from chreos.output import table


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option("--fix", is_flag=True, help="Rewrite stale name/project caches first (nothing else).")
@JSON_OPTION
def check(fix, as_json):
    """Validate the whole workspace; exits 1 if any error is found."""
    config, workspace = load_context()
    if fix:
        with workspace_lock(workspace.root):
            for path in fix_caches(workspace):
                click.echo(f"fixed the name/project caches of {path}", err=True)
    findings = check_workspace(workspace, config.bases)
    errors = sum(1 for finding in findings if finding.severity == ERROR)
    warnings = len(findings) - errors

    def relative(path):
        return str(path.relative_to(workspace.root)) if path.is_relative_to(workspace.root) else str(path)

    if wants_json(as_json, config.output_format):
        emit_json({
            "findings": [
                {"severity": f.severity, "path": str(f.path), "item": f.item, "message": f.message} for f in findings
            ],
            "errors": errors,
            "warnings": warnings,
        })
    elif findings:
        for line in table([(f.severity, relative(f.path), f.item or "-", f.message) for f in findings]):
            click.echo(line)
        click.echo(f"{_plural(errors, 'error')}, {_plural(warnings, 'warning')}")
    else:
        click.echo("no problems found")
    if errors:
        raise SystemExit(1)
