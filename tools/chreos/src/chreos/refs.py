"""Item references and `## References` entries (design §6, §9).

An item reference always carries its kind: `task:<name>`, `task:<project>/<name>`,
`decision:<name>` or `decision:<project>/<name>`. Without a project it means
the project of the item holding the reference.
"""

import re
from dataclasses import dataclass, replace

from chreos.errors import ChreosError
from chreos.model import NAME_PATTERN, Kind, validate_name

REF_KINDS = {"task": Kind.TASK, "decision": Kind.DECISION}
REF = re.compile(r"(task|decision):(?:([^/]*)/)?([^/]*)")
QUALIFIED_NAME = re.compile(rf"(?:{NAME_PATTERN.pattern}/)?{NAME_PATTERN.pattern}")
LINK = re.compile(r'\[[^\]\n]+\]\([^()\s]+(?: "[^"\n]*")?\)')
URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://\S+")


@dataclass(frozen=True)
class ItemRef:
    kind: Kind
    project: str | None
    name: str

    def __str__(self) -> str:
        project = f"{self.project}/" if self.project else ""
        return f"{self.kind}:{project}{self.name}"

    def qualified(self, holder_project: str) -> "ItemRef":
        """The same reference with its project made explicit."""
        return self if self.project else replace(self, project=holder_project)

    def relative_to(self, holder_project: str) -> "ItemRef":
        """The shortest form as written by an item of `holder_project`."""
        return replace(self, project=None) if self.project == holder_project else self


def _hint(text: str) -> str:
    if QUALIFIED_NAME.fullmatch(text):
        return f"; did you mean 'task:{text}' or 'decision:{text}'?"
    return ""


def parse_ref(text: str) -> ItemRef:
    match = REF.fullmatch(text)
    try:
        if match is None:
            raise ChreosError
        kind, project, name = match.groups()
        if project is not None:
            validate_name(project)
        validate_name(name)
    except ChreosError:
        raise ChreosError(
            f"invalid item reference {text!r}: use task:<name>, task:<project>/<name>, "
            f"decision:<name> or decision:<project>/<name>{_hint(text)}"
        ) from None
    return ItemRef(REF_KINDS[kind], project, name)


def classify_reference(text: str) -> str:
    """Kind of a `## References` entry: 'link', 'url' or 'item'."""
    if LINK.fullmatch(text):
        return "link"
    if URL.fullmatch(text):
        return "url"
    if REF.fullmatch(text):
        parse_ref(text)
        return "item"
    raise ChreosError(
        f"invalid reference {text!r}: use a Markdown link [text](target), a URL "
        f"(scheme://...), or an item reference (task:<name>, decision:<name>){_hint(text)}"
    )


def validate_reference(workspace, holder_project: str, text: str) -> str:
    """Validate a `## References` entry written by an item of `holder_project` (§9)."""
    kind = classify_reference(text)
    if kind == "item" and workspace.resolve(parse_ref(text), holder_project) is None:
        raise ChreosError(f"reference {text!r} does not resolve to an existing item")
    return kind
