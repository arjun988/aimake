"""Rendering utilities for graphs and output."""

from __future__ import annotations

from aimake.graph.dag import Graph


def render_ascii_graph(graph: Graph) -> str:
    """Render dependency graph as ASCII art."""
    lines: list[str] = []
    order = graph.names()

    for i, name in enumerate(order):
        node = graph.get(name)
        if i > 0:
            lines.append("   │")
            lines.append("   ▼")
        lines.append(f" {name}")

        # Show branching for multiple dependents
        if len(node.dependents) > 1:
            lines.append("   │")
            branch = "   ├" + "─" * 10 + "┐"
            lines.append(branch)

    return "\n".join(lines)


def render_plan_lines(plan) -> list[str]:
    """Render build plan as text lines."""
    lines = []
    for entry in plan.entries:
        if entry.action.value == "skip":
            symbol = "✓ cached"
        elif entry.action.value == "run":
            symbol = "→ rebuild"
        else:
            symbol = "↻ restore"
        lines.append(f"{entry.name:<20} {symbol}")
    return lines
