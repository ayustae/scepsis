"""Reference rewriting after rename, move and delete (design §7).

One rule covers every case: each item reference (in `dependencies` and in
the `## References` section of tasks) is resolved against its holder's
project *before* the operation, mapped to the item's new identity, and
written back relative to the holder's project *after* the operation.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from chreos.errors import ChreosError, FormatError
from chreos.frontmatter import load, save
from chreos.graph import Node
from chreos.items import LoadFailure
from chreos.lists import ListKind, map_items, read_items
from chreos.model import Kind
from chreos.refs import ItemRef, parse_ref
from chreos.timestamps import now
from chreos.workspace import Workspace

NodeMap = Mapping[Node, Node | None]

@dataclass
class Report:
    changed: list[Path] = field(default_factory=list)
    skipped: list[LoadFailure] = field(default_factory=list)

def snapshot(workspace: Workspace) -> list[tuple[Node, Path]]:
    """Every task (live and archived) and decision, taken before an operation."""
    items = []
    for project in workspace.projects():
        for name in workspace.task_names(project):
            items.append((Node(Kind.TASK, project, name), workspace.live_task_file(project, name)))
        for name in workspace.task_names(project, archived=True):
            items.append((Node(Kind.TASK, project, name), workspace.archived_task_file(project, name)))
        for name in workspace.decision_names(project):
            items.append((Node(Kind.DECISION, project, name), workspace.decision_file(project, name)))
    return items

def _mapper(old_holder: Node, new_holder: Node, node_map: NodeMap):
    def remap(text: str) -> str | None:
        try:
            target = Node.of(parse_ref(text), old_holder.project)
        except ChreosError:
            return text  # links, URLs and invalid entries are left alone
        mapped = node_map.get(target, target)
        if mapped is None:
            return None
        if mapped == target and old_holder.project == new_holder.project:
            return text  # keep the original spelling
        return str(ItemRef(mapped.kind, mapped.project, mapped.name).relative_to(new_holder.project))

    return remap

def _new_path(workspace: Workspace, node: Node) -> Path | None:
    located = workspace.resolve(ItemRef(node.kind, node.project, node.name), node.project)
    return located.path if located else None

def rewrite(workspace: Workspace, before: list[tuple[Node, Path]], node_map: NodeMap) -> Report:
    """Fix every reference after the filesystem change; save changed files only."""
    report = Report()
    for old_holder, _ in before:
        new_holder = node_map.get(old_holder, old_holder)
        if new_holder is None:
            continue
        path = _new_path(workspace, new_holder)
        if path is None:
            continue
        try:
            doc = load(path)
        except (FormatError, OSError) as error:
            report.skipped.append(LoadFailure(path, str(error)))
            continue
        remap = _mapper(old_holder, new_holder, node_map)
        changed = False
        dependencies = doc.meta.get("dependencies")
        if isinstance(dependencies, list):
            for index in reversed(range(len(dependencies))):
                entry = dependencies[index]
                if not isinstance(entry, str):
                    continue
                result = remap(entry)
                if result is None:
                    del dependencies[index]
                    changed = True
                elif result != entry:
                    dependencies[index] = result
                    changed = True
        if new_holder.kind is Kind.TASK:
            body = map_items(doc.body, "References", ListKind.BULLETS, remap)
            if body != doc.body:
                doc.body = body
                changed = True
        if changed:
            doc.meta["updated"] = now()
            save(path, doc)
            report.changed.append(path)
    return report

def referrers(workspace: Workspace, targets: set[Node]) -> list[Node]:
    """Items whose `dependencies` or `## References` point at any of `targets`."""
    found = []
    for holder, path in snapshot(workspace):
        try:
            doc = load(path)
        except (FormatError, OSError):
            continue
        entries = [e for e in doc.meta.get("dependencies") or [] if isinstance(e, str)]
        if holder.kind is Kind.TASK:
            entries += [item.text for item in read_items(doc.body, "References", ListKind.BULLETS)]
        for entry in entries:
            try:
                if Node.of(parse_ref(entry), holder.project) in targets:
                    found.append(holder)
                    break
            except ChreosError:
                continue
    return found
