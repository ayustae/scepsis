"""Dependency graph over tasks and decisions across projects (design §6).

Built from the files on demand, never stored. An item's identity comes from
its path (authoritative, §4), not from its `name`/`project` caches. Broken
files and bad references are collected, never fatal; an unresolved or
unknown dependency counts as unsatisfied.
"""

from dataclasses import dataclass, field
from pathlib import Path

from chreos.errors import ChreosError
from chreos.items import LoadFailure, load_items
from chreos.model import DecisionStatus, Kind, TaskStatus
from chreos.refs import ItemRef, parse_ref
from chreos.workspace import Workspace

CLOSED_TASK_STATUSES = {TaskStatus.DONE, TaskStatus.CANCELLED}


@dataclass(frozen=True, order=True)
class Node:
    kind: Kind
    project: str
    name: str

    def __str__(self) -> str:
        return f"{self.kind}:{self.project}/{self.name}"

    @classmethod
    def of(cls, ref: ItemRef, holder_project: str) -> "Node":
        qualified = ref.qualified(holder_project)
        return cls(qualified.kind, qualified.project, qualified.name)


@dataclass(frozen=True)
class DependencyStatus:
    ref: str
    target: Node | None
    status: str | None
    satisfied: bool


@dataclass(frozen=True)
class GraphProblem:
    node: Node
    message: str

    def __str__(self) -> str:
        return f"{self.node}: {self.message}"


@dataclass
class _Entry:
    path: Path
    archived: bool
    status: str | None = None
    edges: list[tuple[str, Node | None]] = field(default_factory=list)


class Graph:
    def __init__(self):
        self._entries: dict[Node, _Entry] = {}
        self.failures: list[LoadFailure] = []
        self.problems: list[GraphProblem] = []

    @classmethod
    def load(cls, workspace: Workspace) -> "Graph":
        graph = cls()
        dependencies: dict[Node, object] = {}
        for project in workspace.projects():
            groups = [
                (Kind.TASK, False, workspace.task_names(project), workspace.live_task_file),
                (Kind.TASK, True, workspace.task_names(project, archived=True), workspace.archived_task_file),
                (Kind.DECISION, False, workspace.decision_names(project), workspace.decision_file),
            ]
            for kind, archived, names, path_of in groups:
                paths = {path_of(project, name): name for name in names}
                for name in names:
                    graph._entries[Node(kind, project, name)] = _Entry(path_of(project, name), archived)
                items, failures = load_items(paths, kind)
                graph.failures.extend(failures)
                for item in items:
                    node = Node(kind, project, paths[item.path])
                    status = item.doc.meta.get("status")
                    graph._entries[node].status = status if isinstance(status, str) else None
                    dependencies[node] = item.doc.meta.get("dependencies") or []
        for node, refs in dependencies.items():
            graph._add_edges(node, refs)
        return graph

    def _add_edges(self, node: Node, refs: object) -> None:
        if not isinstance(refs, list):
            return  # reported by the schema check
        for text in refs:
            if not isinstance(text, str):
                continue  # reported by the schema check
            try:
                target = Node.of(parse_ref(text), node.project)
            except ChreosError as error:
                self.problems.append(GraphProblem(node, f"dependency {error}"))
                self._entries[node].edges.append((text, None))
                continue
            if target not in self._entries:
                self.problems.append(GraphProblem(node, f"dependency '{text}' does not resolve"))
                target = None
            self._entries[node].edges.append((text, target))

    # Queries

    def __contains__(self, node: Node) -> bool:
        return node in self._entries

    def status(self, node: Node) -> str | None:
        entry = self._entries.get(node)
        return entry.status if entry else None

    def is_archived(self, node: Node) -> bool:
        return node in self._entries and self._entries[node].archived

    def is_satisfied(self, node: Node | None) -> bool:
        if node is None:
            return False
        status = self.status(node)
        if node.kind is Kind.TASK:
            return status in CLOSED_TASK_STATUSES
        return status == DecisionStatus.DECIDED

    def dependency_statuses(self, node: Node) -> list[DependencyStatus]:
        return [
            DependencyStatus(text, target, self.status(target) if target else None, self.is_satisfied(target))
            for text, target in self._entries[node].edges
        ]

    def statuses_for(self, holder_project: str, refs: list[str]) -> list[DependencyStatus]:
        """Statuses of references not yet saved (e.g. dependencies being written)."""
        result = []
        for text in refs:
            try:
                target = Node.of(parse_ref(text), holder_project)
            except ChreosError:
                target = None
            if target is not None and target not in self._entries:
                target = None
            status = self.status(target) if target else None
            result.append(DependencyStatus(text, target, status, self.is_satisfied(target)))
        return result

    def dependents(self, node: Node) -> list[Node]:
        return sorted(
            other
            for other, entry in self._entries.items()
            if any(target == node for _, target in entry.edges)
        )

    def ready_tasks(self) -> list[Node]:
        return sorted(
            node
            for node, entry in self._entries.items()
            if node.kind is Kind.TASK
            and not entry.archived
            and entry.status is not None
            and entry.status not in CLOSED_TASK_STATUSES
            and all(self.is_satisfied(target) for _, target in entry.edges)
        )

    # Writes and checks

    def _path_between(self, start: Node, goal: Node, extra: dict[Node, list[Node]]) -> list[Node] | None:
        """A dependency path from `start` to `goal`, if any (iterative DFS)."""
        stack = [(start, [start])]
        seen = set()
        while stack:
            current, path = stack.pop()
            if current == goal:
                return path
            if current in seen:
                continue
            seen.add(current)
            entry = self._entries.get(current)
            targets = [t for _, t in entry.edges if t] if entry else []
            for target in [*targets, *extra.get(current, [])]:
                stack.append((target, [*path, target]))
        return None

    def check_new_dependencies(self, node: Node, refs: list[str]) -> list[ItemRef]:
        """Validate dependencies being added to `node`: they resolve and create no cycle."""
        parsed, added = [], {node: []}
        for text in refs:
            ref = parse_ref(text)
            target = Node.of(ref, node.project)
            if target == node:
                raise ChreosError(f"{node} cannot depend on itself")
            if target not in self._entries:
                raise ChreosError(f"dependency '{text}' does not resolve to an existing item")
            cycle = self._path_between(target, node, added)
            if cycle:
                chain = " -> ".join(str(n) for n in [node, *cycle])
                raise ChreosError(f"dependency '{text}' would create a cycle: {chain}")
            added[node].append(target)
            parsed.append(ref)
        return parsed

    def find_cycles(self) -> list[list[Node]]:
        """Every dependency cycle once, as the sorted nodes of each strongly connected group.

        Iterative Tarjan's algorithm, so long dependency chains can't exhaust the stack.
        """
        index: dict[Node, int] = {}
        low: dict[Node, int] = {}
        on_stack: set[Node] = set()
        stack: list[Node] = []
        cycles: list[list[Node]] = []

        def targets(node: Node) -> list[Node]:
            return [t for _, t in self._entries[node].edges if t]

        for root in sorted(self._entries):
            if root in index:
                continue
            work = [(root, iter(targets(root)))]
            index[root] = low[root] = len(index)
            stack.append(root)
            on_stack.add(root)
            while work:
                node, pending = work[-1]
                target = next(pending, None)
                if target is not None:
                    if target not in index:
                        index[target] = low[target] = len(index)
                        stack.append(target)
                        on_stack.add(target)
                        work.append((target, iter(targets(target))))
                    elif target in on_stack:
                        low[node] = min(low[node], index[target])
                    continue
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
                if low[node] == index[node]:
                    group = []
                    while True:
                        member = stack.pop()
                        on_stack.discard(member)
                        group.append(member)
                        if member == node:
                            break
                    if len(group) > 1 or node in targets(node):
                        cycles.append(sorted(group))
        return sorted(cycles)
