"""Directed acyclic graph for artifact dependencies."""

from __future__ import annotations

from collections import deque
from typing import Any, Iterator

from aimake.config.schema import AimakeConfig
from aimake.graph.node import Node


class GraphError(Exception):
    """Raised when the dependency graph is invalid."""


class Graph:
    """Dependency DAG built from project configuration."""

    def __init__(self, nodes: dict[str, Node]) -> None:
        self._nodes = nodes

    @classmethod
    def from_config(cls, config: AimakeConfig) -> Graph:
        """Build a graph from validated configuration."""
        nodes: dict[str, Node] = {}
        for name, artifact in config.artifacts.items():
            nodes[name] = Node(
                name=name,
                config=artifact,
                dependencies=list(artifact.depends_on),
            )

        # Build reverse edges (dependents)
        for name, node in nodes.items():
            for dep in node.dependencies:
                if dep not in nodes:
                    raise GraphError(
                        f"Artifact '{name}' depends on unknown artifact '{dep}'"
                    )
                nodes[dep].dependents.append(name)

        graph = cls(nodes)
        cycle = graph.find_cycle()
        if cycle:
            chain = " → ".join(cycle)
            raise GraphError(f"Circular dependency detected: {chain}")
        return graph

    @property
    def nodes(self) -> dict[str, Node]:
        return self._nodes

    def __contains__(self, name: str) -> bool:
        return name in self._nodes

    def __len__(self) -> int:
        return len(self._nodes)

    def get(self, name: str) -> Node:
        if name not in self._nodes:
            raise GraphError(f"Unknown artifact: '{name}'")
        return self._nodes[name]

    def names(self) -> list[str]:
        """Return artifact names in topological order."""
        return [n.name for n in self.topological_sort()]

    def topological_sort(self) -> list[Node]:
        """Return nodes in topological order (dependencies first)."""
        in_degree = {name: len(node.dependencies) for name, node in self._nodes.items()}
        queue = deque(name for name, deg in in_degree.items() if deg == 0)
        result: list[Node] = []

        while queue:
            name = queue.popleft()
            result.append(self._nodes[name])
            for dependent in self._nodes[name].dependents:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self._nodes):
            raise GraphError("Circular dependency detected (topological sort failed)")

        return result

    def find_cycle(self) -> list[str] | None:
        """Detect cycles using DFS. Returns cycle path if found."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {name: WHITE for name in self._nodes}
        parent: dict[str, str | None] = {name: None for name in self._nodes}

        def dfs(node: str) -> list[str] | None:
            color[node] = GRAY
            for dep in self._nodes[node].dependencies:
                if color[dep] == GRAY:
                    # Reconstruct cycle
                    cycle = [dep, node]
                    current = node
                    while parent[current] and parent[current] != dep:
                        current = parent[current]  # type: ignore[assignment]
                        cycle.append(current)
                    cycle.append(dep)
                    cycle.reverse()
                    return cycle
                if color[dep] == WHITE:
                    parent[dep] = node
                    result = dfs(dep)
                    if result:
                        return result
            color[node] = BLACK
            return None

        for name in self._nodes:
            if color[name] == WHITE:
                cycle = dfs(name)
                if cycle:
                    return cycle
        return None

    def ancestors(self, name: str) -> list[str]:
        """Return all transitive dependencies of an artifact."""
        if name not in self._nodes:
            raise GraphError(f"Unknown artifact: '{name}'")
        visited: set[str] = set()
        queue = deque(self._nodes[name].dependencies)
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            queue.extend(self._nodes[current].dependencies)
        return sorted(visited)

    def descendants(self, name: str) -> list[str]:
        """Return all transitive dependents of an artifact."""
        if name not in self._nodes:
            raise GraphError(f"Unknown artifact: '{name}'")
        visited: set[str] = set()
        queue = deque(self._nodes[name].dependents)
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            queue.extend(self._nodes[current].dependents)
        return sorted(visited)

    def subgraph_for_targets(self, targets: list[str]) -> Graph:
        """Return subgraph containing targets and all their dependencies."""
        needed: set[str] = set()
        for target in targets:
            if target not in self._nodes:
                raise GraphError(f"Unknown target: '{target}'")
            needed.add(target)
            needed.update(self.ancestors(target))

        sub_nodes = {
            name: Node(
                name=node.name,
                config=node.config,
                dependencies=[d for d in node.dependencies if d in needed],
                dependents=[d for d in node.dependents if d in needed],
            )
            for name, node in self._nodes.items()
            if name in needed
        }
        return Graph(sub_nodes)

    def parallel_groups(self) -> list[list[str]]:
        """Group artifacts into levels that can run in parallel."""
        in_degree = {name: len(node.dependencies) for name, node in self._nodes.items()}
        groups: list[list[str]] = []
        remaining = set(self._nodes.keys())

        while remaining:
            ready = sorted(
                name for name in remaining if all(
                    d not in remaining for d in self._nodes[name].dependencies
                )
            )
            if not ready:
                break
            groups.append(ready)
            for name in ready:
                remaining.remove(name)

        return groups

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {name: node.to_dict() for name, node in self._nodes.items()},
            "order": self.names(),
        }

    def to_dot(self) -> str:
        """Export graph as Graphviz DOT format."""
        lines = ["digraph aimake {"]
        lines.append('  rankdir=TB;')
        lines.append('  node [shape=box];')
        for name, node in self._nodes.items():
            label = f"{name}\\n({node.config.type})"
            lines.append(f'  "{name}" [label="{label}"];')
            for dep in node.dependencies:
                lines.append(f'  "{dep}" -> "{name}";')
        lines.append("}")
        return "\n".join(lines)

    def __iter__(self) -> Iterator[Node]:
        return iter(self.topological_sort())
