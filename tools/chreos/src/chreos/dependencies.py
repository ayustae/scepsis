"""Changing and checking an item's `dependencies` (design §6), shared by tasks and decisions."""

from collections.abc import Iterable, MutableMapping

from chreos.errors import ChreosError
from chreos.graph import Graph, Node
from chreos.refs import parse_ref
from chreos.workspace import Workspace


def target(text: str, project: str) -> Node | None:
    """The item a reference points to, or None if it isn't a valid reference."""
    try:
        return Node.of(parse_ref(text), project)
    except ChreosError:
        return None


def apply_dependency_changes(
    meta: MutableMapping, graph: Graph, node: Node, *, add: Iterable[str], remove: Iterable[str]
) -> list[str]:
    """Remove (by target) and add dependencies in place; additions must resolve and create no cycle."""
    warnings = []
    dependencies = meta.get("dependencies")
    if not isinstance(dependencies, list):
        dependencies = meta["dependencies"] = []
    for text in remove:
        wanted = target(text, node.project)
        matching = [
            index for index, entry in enumerate(dependencies)
            if wanted and isinstance(entry, str) and target(entry, node.project) == wanted
        ]
        if not matching:
            warnings.append(f"'{text}' is not a dependency of {node}")
        for index in reversed(matching):
            del dependencies[index]
    present = {t for entry in dependencies if isinstance(entry, str) and (t := target(entry, node.project))}
    new = []
    for text in add:
        found = target(text, node.project)
        if found is None or found not in present:  # invalid ones are rejected below
            new.append(text)
            present.add(found)
    graph.check_new_dependencies(node, new)
    dependencies.extend(new)
    return warnings


def dependency_checks(workspace: Workspace, node: Node) -> list[str]:
    """Errors for `edit`: unresolved dependencies and cycles through `node`."""
    graph = Graph.load(workspace)
    errors = [problem.message for problem in graph.problems if problem.node == node]
    for cycle in graph.find_cycles():
        if node in cycle:
            errors.append(f"dependency cycle: {' -> '.join(str(n) for n in cycle)}")
    return errors
