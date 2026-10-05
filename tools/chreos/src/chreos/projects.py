"""Project operations (design §2, §12.2)."""

from collections.abc import Iterable
from pathlib import Path

from chreos.errors import ChreosError
from chreos.frontmatter import save
from chreos.model import Kind, ProjectStatus, normalize_labels, validate_name
from chreos.templates import render
from chreos.workspace import Workspace


def parse_project_status(value: str) -> ProjectStatus:
    try:
        return ProjectStatus(value)
    except ValueError:
        allowed = ", ".join(ProjectStatus)
        raise ChreosError(f"invalid project status {value!r} (allowed: {allowed})") from None


def create_project(
    workspace: Workspace,
    name: str,
    *,
    title: str | None = None,
    summary: str | None = None,
    labels: Iterable[str] = (),
    status: str = ProjectStatus.ACTIVE,
) -> Path:
    """Create a project folder with its subfolders and PROJECT.md. Caller holds the lock."""
    validate_name(name)
    fields = {"status": parse_project_status(status), "labels": normalize_labels(labels)}
    if not workspace.root.is_dir():
        raise ChreosError(f"the workspace {workspace.root} does not exist; run 'chreos init'")
    workspace.ensure_free(Kind.PROJECT, None, name)
    doc = render(Kind.PROJECT, name=name, title=title, summary=summary, fields=fields)
    workspace.project_dir(name).mkdir(exist_ok=True)
    workspace.ensure_project_dirs(name)
    path = workspace.project_file(name)
    save(path, doc)
    return path
