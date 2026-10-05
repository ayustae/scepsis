"""Workspace layout, discovery, lookup and uniqueness (design §2, §6).

Every name is validated before it becomes part of a path, so user input can
never point outside the workspace.
"""

from dataclasses import dataclass
from pathlib import Path

from chreos.errors import ChreosError
from chreos.model import Kind, is_valid_name, validate_name
from chreos.refs import ItemRef

PROJECT_FILE = "PROJECT.md"
TASK_FILE = "TASK.md"
TASKS, ARCHIVE, DECISIONS = "tasks", ".archive", "decisions"
LOCK_FILE = ".scepsis.lock"


@dataclass(frozen=True)
class Located:
    kind: Kind
    project: str
    name: str
    path: Path
    archived: bool


def _sorted_names(names) -> list[str]:
    return sorted(name for name in names if is_valid_name(name))


class Workspace:
    def __init__(self, root: Path):
        self.root = Path(root)

    # Paths

    @property
    def lock_file(self) -> Path:
        return self.root / LOCK_FILE

    def project_dir(self, project: str) -> Path:
        return self.root / validate_name(project)

    def project_file(self, project: str) -> Path:
        return self.project_dir(project) / PROJECT_FILE

    def tasks_dir(self, project: str) -> Path:
        return self.project_dir(project) / TASKS

    def archive_dir(self, project: str) -> Path:
        return self.project_dir(project) / ARCHIVE

    def decisions_dir(self, project: str) -> Path:
        return self.project_dir(project) / DECISIONS

    def live_task_file(self, project: str, name: str) -> Path:
        return self.tasks_dir(project) / validate_name(name) / TASK_FILE

    def archived_task_file(self, project: str, name: str) -> Path:
        return self.archive_dir(project) / f"{validate_name(name)}.md"

    def decision_file(self, project: str, name: str) -> Path:
        return self.decisions_dir(project) / f"{validate_name(name)}.md"

    # Discovery

    def projects(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return _sorted_names(
            entry.name
            for entry in self.root.iterdir()
            if entry.is_dir() and (entry / PROJECT_FILE).is_file()
        )

    def task_names(self, project: str, archived: bool = False) -> list[str]:
        if archived:
            return self._md_stems(self.archive_dir(project))
        folder = self.tasks_dir(project)
        if not folder.is_dir():
            return []
        return _sorted_names(
            entry.name for entry in folder.iterdir() if (entry / TASK_FILE).is_file()
        )

    def decision_names(self, project: str) -> list[str]:
        return self._md_stems(self.decisions_dir(project))

    @staticmethod
    def _md_stems(folder: Path) -> list[str]:
        if not folder.is_dir():
            return []
        return _sorted_names(
            entry.stem for entry in folder.iterdir() if entry.suffix == ".md" and entry.is_file()
        )

    def ensure_project_dirs(self, project: str) -> None:
        for folder in (self.tasks_dir, self.archive_dir, self.decisions_dir):
            folder(project).mkdir(exist_ok=True)

    # Uniqueness

    def project_exists(self, project: str) -> bool:
        return self.project_file(project).is_file()

    def task_exists(self, project: str, name: str) -> bool:
        return (
            self.live_task_file(project, name).is_file()
            or self.archived_task_file(project, name).is_file()
        )

    def decision_exists(self, project: str, name: str) -> bool:
        return self.decision_file(project, name).is_file()

    def ensure_free(self, kind: Kind, project: str | None, name: str) -> None:
        if kind is Kind.PROJECT:
            if self.project_exists(name):
                raise ChreosError(f"project '{name}' already exists")
        elif kind is Kind.TASK:
            if self.live_task_file(project, name).is_file():
                raise ChreosError(f"task '{project}/{name}' already exists")
            if self.archived_task_file(project, name).is_file():
                raise ChreosError(f"task '{project}/{name}' already exists (archived)")
        elif self.decision_exists(project, name):
            raise ChreosError(f"decision '{project}/{name}' already exists")

    # Lookup

    @staticmethod
    def parse_item_name(text: str, default_project: str) -> tuple[str, str]:
        """A command NAME argument: `<name>` or `<project>/<name>` (§6)."""
        parts = text.split("/")
        if len(parts) > 2 or not all(is_valid_name(part) for part in parts):
            raise ChreosError(f"invalid item name {text!r}: use <name> or <project>/<name>")
        if len(parts) == 1:
            return default_project, parts[0]
        return parts[0], parts[1]

    def resolve_item_name(self, text: str, project_opt: str | None, default_project: str) -> tuple[str, str]:
        """NAME plus `-P`: `-P` (or the default project) applies to a bare name;
        a qualified name must not contradict `-P`."""
        project, name = self.parse_item_name(text, project_opt or default_project)
        if project_opt and "/" in text and project != project_opt:
            raise ChreosError(f"'{text}' conflicts with -P {project_opt}")
        return project, name

    def resolve(self, ref: ItemRef, holder_project: str) -> Located | None:
        project = ref.project or holder_project
        if ref.kind is Kind.TASK:
            candidates = [
                (self.live_task_file(project, ref.name), False),
                (self.archived_task_file(project, ref.name), True),
            ]
        else:
            candidates = [(self.decision_file(project, ref.name), False)]
        for path, archived in candidates:
            if path.is_file():
                return Located(ref.kind, project, ref.name, path, archived)
        return None
