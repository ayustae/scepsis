"""Item templates (design §8).

The packaged templates under `chreos/templates/` are copies of the
repository's `templates/` folder. A file of the same name in
`~/.scepsis/templates/` overrides one; it must keep the original's keys.
Values are set as YAML data, never by textual substitution, so any title
or summary stays valid YAML.
"""

import re
from datetime import datetime
from importlib.resources import files

from chreos.errors import ChreosError, FormatError
from chreos.frontmatter import Document, parse
from chreos.model import Kind
from chreos.paths import scepsis_home
from chreos.timestamps import now

TEMPLATE_FILES = {
    Kind.PROJECT: "PROJECT.md",
    Kind.TASK: "TASK.md",
    Kind.DECISION: "DECISION.md",
}
PLACEHOLDER = re.compile(r"<([a-z_]+)>")


def packaged_template(kind: Kind) -> str:
    return files("chreos").joinpath("templates", TEMPLATE_FILES[kind]).read_text(encoding="utf-8")


def _template(kind: Kind) -> Document:
    packaged = parse(packaged_template(kind))
    override = scepsis_home() / "templates" / TEMPLATE_FILES[kind]
    if not override.is_file():
        return packaged
    try:
        doc = parse(override.read_text(encoding="utf-8"))
    except (FormatError, UnicodeDecodeError) as error:
        raise ChreosError(f"invalid template override {override}: {error}") from None
    missing = [key for key in packaged.meta if key not in doc.meta]
    if missing:
        raise ChreosError(
            f"invalid template override {override}: missing keys {', '.join(missing)}"
        )
    return doc


def _drop_summary_line(body: str) -> str:
    lines = body.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.strip() == "<summary>":
            del lines[index]
            if index < len(lines) and not lines[index].strip():
                del lines[index]
            elif index > 0 and not lines[index - 1].strip():
                del lines[index - 1]
            break
    return "".join(lines)


def render(
    kind: Kind,
    *,
    name: str,
    title: str | None = None,
    summary: str | None = None,
    project: str | None = None,
    timestamp: datetime | None = None,
    fields: dict | None = None,
) -> Document:
    """Render a new item from its template. `fields` sets other template keys."""
    if kind is not Kind.PROJECT and project is None:
        raise ChreosError(f"a {kind} needs a project")
    doc = _template(kind)
    stamp = timestamp or now()
    values = {
        "name": name,
        "title": title if title is not None else name,
        "summary": summary,
        "project": project,
        "timestamp": stamp,
    }
    for key, value in doc.meta.items():
        if isinstance(value, str) and (match := PLACEHOLDER.fullmatch(value)):
            placeholder = match.group(1)
            if placeholder not in values:
                raise ChreosError(f"unknown placeholder <{placeholder}> in the {kind} template")
            doc.meta[key] = values[placeholder]
    for key, value in (fields or {}).items():
        if key not in doc.meta:
            raise ChreosError(f"field {key!r} is not in the {kind} template")
        doc.meta[key] = value
    body = doc.body if summary is not None else _drop_summary_line(doc.body)
    body = body.replace("<title>", values["title"])
    if summary is not None:
        body = body.replace("<summary>", summary)
    doc.body = body
    return doc
