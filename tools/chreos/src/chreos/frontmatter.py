"""Non-destructive frontmatter round-trip (design §8).

A file is `---`, a YAML mapping, `---`, then the body. Only the mapping is
parsed; the body is kept byte-for-byte. The mapping is loaded in ruamel.yaml
round-trip mode, so comments, key order, quoting and unknown keys survive.
"""

import io
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError
from ruamel.yaml.representer import RoundTripRepresenter

from chreos.errors import FormatError
from chreos.fileio import atomic_write
from chreos.timestamps import format_timestamp

DELIMITER = "---"


class _Representer(RoundTripRepresenter):
    """Representation of values the CLI sets (loaded values keep their own form)."""

    def ignore_aliases(self, data):
        return True

    def represent_none(self, data):
        return self.represent_scalar("tag:yaml.org,2002:null", "null")

    def represent_datetime(self, data):
        return self.represent_scalar("tag:yaml.org,2002:timestamp", format_timestamp(data))

    def represent_str_enum(self, data):
        return self.represent_str(str(data.value))


_Representer.add_representer(type(None), _Representer.represent_none)
_Representer.add_representer(datetime, _Representer.represent_datetime)
_Representer.add_multi_representer(StrEnum, _Representer.represent_str_enum)


def _yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.Representer = _Representer
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.preserve_quotes = True
    yaml.width = 1_000_000
    return yaml


@dataclass
class Document:
    meta: CommentedMap
    body: str
    newline: str = "\n"

    @classmethod
    def new(cls, meta: dict, body: str) -> "Document":
        return cls(CommentedMap(meta), body)


def parse(text: str) -> Document:
    """Split `text` into frontmatter and body; raise `FormatError` if it can't be parsed."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != DELIMITER:
        raise FormatError("no frontmatter: the file must start with a '---' line")
    newline = lines[0][len(DELIMITER) :] or "\n"
    for index, line in enumerate(lines[1:], start=1):
        if line.rstrip("\r\n") == DELIMITER:
            break
    else:
        raise FormatError("unterminated frontmatter: no closing '---' line")
    yaml_text = "".join(lines[1:index]).replace("\r\n", "\n")
    try:
        meta = _yaml().load(yaml_text)
    except YAMLError as error:
        raise FormatError(f"invalid YAML in frontmatter: {error}") from None
    if not isinstance(meta, CommentedMap):
        raise FormatError("frontmatter must be a YAML mapping")
    return Document(meta, "".join(lines[index + 1 :]), newline)


def dump(doc: Document) -> str:
    stream = io.StringIO()
    _yaml().dump(doc.meta, stream)
    head = f"{DELIMITER}\n{stream.getvalue()}{DELIMITER}\n"
    if doc.newline != "\n":
        head = head.replace("\n", doc.newline)
    return head + doc.body


def load(path: Path) -> Document:
    try:
        return parse(Path(path).read_text(encoding="utf-8"))
    except FormatError as error:
        raise FormatError(f"{path}: {error}") from None
    except UnicodeDecodeError:
        raise FormatError(f"{path}: not valid UTF-8") from None


def save(path: Path, doc: Document) -> None:
    atomic_write(path, dump(doc))
