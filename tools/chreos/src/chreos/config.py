"""`~/.scepsis/config.toml` (design §13).

The file is shared by the whole Scepsis framework: only the keys below
belong to chreos; anything else is preserved and ignored. Paths are stored
as written (e.g. `~/code`) and expanded when loaded.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError

from chreos.errors import ChreosError
from chreos.fileio import atomic_write
from chreos.model import NONE, SourceType, validate_name
from chreos.paths import parse_path, scepsis_home
from chreos.workspace import Workspace

OUTPUT_FORMATS = ("text", "json")


def _check_format(value: str) -> str:
    if value not in OUTPUT_FORMATS:
        raise ChreosError(f"invalid output format {value!r} (allowed: {', '.join(OUTPUT_FORMATS)})")
    return value


@dataclass(frozen=True)
class Key:
    required: bool
    check: Callable[[str], object]
    help: str


KEYS = {
    "workspace.path": Key(True, parse_path, "Root of the workspace; project folders live directly under it."),
    "defaults.project": Key(True, validate_name, "Project used when a command gets no -P/--project."),
    "source.git_path": Key(False, parse_path, "Base folder that relative git task sources are resolved against."),
    "source.local_path": Key(False, parse_path, "Base folder that relative local task sources are resolved against."),
    "output.format": Key(False, _check_format, 'Default output: "text" or "json"; --json overrides it per invocation.'),
}
EXAMPLES = {"source.git_path": "~/code", "source.local_path": "~/files", "output.format": "text"}


@dataclass(frozen=True)
class Config:
    workspace: Path
    default_project: str
    bases: dict[SourceType, Path | None]
    output_format: str


def config_path() -> Path:
    return scepsis_home() / "config.toml"


def _read_document() -> tomlkit.TOMLDocument:
    path = config_path()
    if not path.is_file():
        raise ChreosError(f"no configuration at {path}: run 'chreos init'")
    try:
        return tomlkit.parse(path.read_text(encoding="utf-8"))
    except (TOMLKitError, UnicodeDecodeError) as error:
        raise ChreosError(f"{path}: invalid TOML: {error}") from None


def _known(key: str) -> Key:
    if key not in KEYS:
        raise ChreosError(f"unknown key {key!r} (known keys: {', '.join(KEYS)})")
    return KEYS[key]


def _raw(doc, key: str) -> object:
    section, field = key.split(".")
    table = doc.get(section)
    if not isinstance(table, dict):
        return None
    value = table.get(field)
    return value.unwrap() if hasattr(value, "unwrap") else value


def _checked(key: str, value: object) -> str:
    try:
        if not isinstance(value, str):
            raise ChreosError("must be a string")
        KEYS[key].check(value)
    except ChreosError as error:
        raise ChreosError(f"{config_path()}: invalid {key}: {error}") from None
    return value


def load_config() -> Config:
    doc = _read_document()
    values = {}
    for key, spec in KEYS.items():
        value = _raw(doc, key)
        if value is None:
            if spec.required:
                raise ChreosError(f"{config_path()}: missing required key {key}")
            continue
        values[key] = _checked(key, value)
    return Config(
        workspace=parse_path(values["workspace.path"]),
        default_project=values["defaults.project"],
        bases={
            SourceType.GIT: parse_path(values["source.git_path"]) if "source.git_path" in values else None,
            SourceType.LOCAL: parse_path(values["source.local_path"]) if "source.local_path" in values else None,
        },
        output_format=values.get("output.format", "text"),
    )


def get_value(key: str) -> str | None:
    _known(key)
    value = _raw(_read_document(), key)
    return None if value is None else _checked(key, value)


def set_value(key: str, raw: str) -> None:
    """Change one key (`none` removes an optional one), validated, keeping comments."""
    spec = _known(key)
    doc = _read_document()
    section, field = key.split(".")
    if raw == NONE:
        if spec.required:
            raise ChreosError(f"{key} is required and cannot be removed")
        table = doc.get(section)
        if isinstance(table, dict) and field in table:
            del table[field]
    else:
        spec.check(raw)
        if key == "workspace.path" and not parse_path(raw).is_dir():
            raise ChreosError(f"workspace folder {parse_path(raw)} does not exist")
        if key == "defaults.project":
            workspace = Workspace(parse_path(_checked("workspace.path", _raw(doc, "workspace.path"))))
            if not workspace.project_exists(raw):
                raise ChreosError(f"there is no project '{raw}' in the workspace {workspace.root}")
        if not isinstance(doc.get(section), dict):
            doc[section] = tomlkit.table()
        doc[section][field] = raw
    atomic_write(config_path(), tomlkit.dumps(doc))


def render_new_config(
    workspace_path: str,
    default_project: str,
    *,
    git_path: str | None = None,
    local_path: str | None = None,
) -> str:
    """The commented, hand-editable config written by `chreos init`."""
    values = {
        "workspace.path": workspace_path,
        "defaults.project": default_project,
        "source.git_path": git_path,
        "source.local_path": local_path,
    }
    doc = tomlkit.document()
    doc.add(tomlkit.comment("Scepsis configuration. Edit by hand or with 'chreos config set KEY VALUE'."))
    doc.add(tomlkit.comment("Paths must be absolute or start with '~'."))
    tables: dict[str, tomlkit.items.Table] = {}
    for key, spec in KEYS.items():
        section, field = key.split(".")
        if section not in tables:
            tables[section] = tomlkit.table()
            doc.add(section, tables[section])
        table = tables[section]
        table.add(tomlkit.comment(spec.help))
        value = values.get(key)
        if value is None:
            table.add(tomlkit.comment(f'{field} = "{EXAMPLES[key]}"'))
        else:
            table.add(field, value)
    return tomlkit.dumps(doc)


def set_values() -> dict[str, str]:
    """The known keys that are set, in documentation order, validated."""
    doc = _read_document()
    return {
        key: _checked(key, value)
        for key in KEYS
        if (value := _raw(doc, key)) is not None
    }
