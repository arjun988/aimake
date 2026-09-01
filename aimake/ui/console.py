"""Rich console output for aimake."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from aimake.models import (
    ArtifactStatus,
    BuildAction,
    BuildPlan,
    BuildResult,
    ExplainResult,
)

# ASCII fallbacks when the terminal cannot render Unicode symbols
_OK = "✓" if sys.platform != "win32" else "+"
_ERR = "✗" if sys.platform != "win32" else "x"
_ARROW = "→" if sys.platform != "win32" else "->"
_RESTORE = "↻" if sys.platform != "win32" else "~>"

SYMBOL_CACHED = f"{_OK} cached" if sys.platform != "win32" else "+ cached"
SYMBOL_REBUILD = f"{_ARROW} rebuild"
SYMBOL_RESTORE = f"{_RESTORE} restore"

rich_console = Console()

# Backward-compatible alias used throughout this module
console = rich_console


def print(*args, **kwargs) -> None:
    """Print to the aimake Rich console."""
    rich_console.print(*args, **kwargs)


def print_header(title: str = "AIMAKE") -> None:
    rich_console.print()
    rich_console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))


def print_success(message: str) -> None:
    rich_console.print(f"[green]{_OK}[/green] {message}")


def print_error(message: str) -> None:
    rich_console.print(f"[red]{_ERR}[/red] {message}")


def print_warning(message: str) -> None:
    rich_console.print(f"[yellow]![/yellow] {message}")


def print_info(message: str) -> None:
    rich_console.print(f"[dim]{message}[/dim]")


def status_label(status: ArtifactStatus) -> Text:
    colors = {
        ArtifactStatus.UP_TO_DATE: "green",
        ArtifactStatus.CACHED: "green",
        ArtifactStatus.CHANGED: "yellow",
        ArtifactStatus.STALE: "red",
        ArtifactStatus.UNKNOWN: "dim",
        ArtifactStatus.BUILDING: "blue",
        ArtifactStatus.SUCCESS: "green",
        ArtifactStatus.FAILED: "red",
    }
    labels = {
        ArtifactStatus.UP_TO_DATE: "UNCHANGED",
        ArtifactStatus.CACHED: "CACHED",
        ArtifactStatus.CHANGED: "CHANGED",
        ArtifactStatus.STALE: "STALE",
        ArtifactStatus.UNKNOWN: "UNKNOWN",
        ArtifactStatus.BUILDING: "BUILDING",
        ArtifactStatus.SUCCESS: "SUCCESS",
        ArtifactStatus.FAILED: "FAILED",
    }
    color = colors.get(status, "white")
    label = labels.get(status, status.value.upper())
    return Text(label, style=color)


def action_label(action: BuildAction) -> Text:
    colors = {
        BuildAction.SKIP: "dim",
        BuildAction.RUN: "cyan",
        BuildAction.RESTORE: "green",
    }
    labels = {
        BuildAction.SKIP: "SKIP",
        BuildAction.RUN: "RUN",
        BuildAction.RESTORE: "RESTORE",
    }
    return Text(labels.get(action, action.value), style=colors.get(action, "white"))


def print_status_table(
    names: list[str],
    statuses: dict[str, ArtifactStatus],
) -> None:
    for name in names:
        status = statuses.get(name, ArtifactStatus.UNKNOWN)
        rich_console.print(f"  {name:<30} {status_label(status)}")


def print_build_plan(plan: BuildPlan) -> None:
    rich_console.print("\n[bold]Build plan:[/bold]\n")
    for entry in plan.entries:
        rich_console.print(f"  {action_label(entry.action)}  {entry.name}")


def print_build_summary(result: BuildResult) -> None:
    rich_console.print()
    if result.success:
        rich_console.print(
            f"[green]Build completed[/green] in [bold]{result.duration:.1f}s[/bold]"
        )
    else:
        rich_console.print(
            f"[red]Build failed[/red] after [bold]{result.duration:.1f}s[/bold]"
        )
    rich_console.print(
        f"\n  {len(result.rebuilt)} rebuilt\n"
        f"  {len(result.reused)} reused\n"
        f"  {len(result.failed)} failed"
    )


def print_metrics(metrics: dict) -> None:
    if not metrics:
        return
    rich_console.print("\n[bold]EVALUATION[/bold]\n")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Value", justify="right")

    formatters = {
        "accuracy": lambda v: f"{float(v):.1%}",
        "f1": lambda v: f"{float(v):.1%}",
        "latency_ms": lambda v: f"{int(v)}ms",
        "cost_usd": lambda v: f"${float(v):.2f}",
    }

    for key, value in metrics.items():
        if isinstance(value, (int, float)):
            fmt = formatters.get(key, str)
            try:
                display = fmt(value)
            except (TypeError, ValueError):
                display = str(value)
            table.add_row(key, display)

    rich_console.print(table)


def print_explain(result: ExplainResult) -> None:
    rich_console.print("\n[bold]WHY IS THIS TARGET STALE?[/bold]\n")
    rich_console.print(f"[cyan]{result.target}[/cyan]")

    if result.chain:
        for i, name in enumerate(result.chain):
            prefix = "   ↓" if i < len(result.chain) - 1 else ""
            rich_console.print(f"   ↓")
            rich_console.print(f"depends on [cyan]{name}[/cyan]")

    if result.root_cause:
        rich_console.print(f"\n[yellow]{result.root_cause}[/yellow]")

    if result.old_fingerprint:
        rich_console.print(f"\nOld fingerprint:\n  {result.old_fingerprint[:40]}...")
    if result.new_fingerprint:
        rich_console.print(f"\nNew fingerprint:\n  {result.new_fingerprint[:40]}...")

    rich_console.print(f"\n[bold]Therefore:[/bold]\n  {result.conclusion}")


def print_graph_ascii(graph) -> None:
    """Print a simple ASCII dependency graph."""
    from aimake.ui.rendering import render_ascii_graph

    rich_console.print(render_ascii_graph(graph))


def print_history_table(builds: list[dict]) -> None:
    table = Table(title="Build History", show_header=True, header_style="bold")
    table.add_column("Build")
    table.add_column("Time")
    table.add_column("Duration")
    table.add_column("Changed")
    table.add_column("Status")

    for build in builds:
        import json
        from datetime import datetime

        ts = build.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts)
            time_str = dt.strftime("%H:%M")
        except (ValueError, TypeError):
            time_str = ts[:5] if ts else "?"

        duration = build.get("duration")
        dur_str = f"{duration:.1f}s" if duration else "?"
        changed = json.loads(build.get("changed_artifacts") or "[]")
        changed_str = ", ".join(changed[:3]) if changed else "-"
        status = build.get("status", "?")
        status_style = "green" if status == "success" else "red"

        table.add_row(
            f"#{build['id']}",
            time_str,
            dur_str,
            changed_str,
            Text(status.upper(), style=status_style),
        )

    rich_console.print(table)


def print_inspect(
    name: str,
    state,
    artifact_type: str,
    *,
    dependencies: list[str] | None = None,
    files: list[str] | None = None,
) -> None:
    rich_console.print("\n[bold]ARTIFACT[/bold]\n")
    rich_console.print(f"Name: [cyan]{name}[/cyan]")
    rich_console.print(f"Type: {artifact_type}")
    rich_console.print(f"Status: {state.status.value if state else 'unknown'}")

    if state and state.created_at:
        rich_console.print(f"\nCreated:\n  {state.created_at.strftime('%Y-%m-%d %H:%M')}")

    if state and state.fingerprint:
        rich_console.print(f"\nFingerprint:\n  {state.fingerprint}")

    if dependencies:
        rich_console.print(f"\nDependencies:\n  {', '.join(dependencies)}")

    if files:
        rich_console.print("\nFiles:")
        for f in files:
            rich_console.print(f"  {f}")

    if state and state.duration:
        rich_console.print(f"\nExecution:\n  duration: {state.duration:.1f}s")

    if state and state.metrics:
        rich_console.print("\nMetrics:")
        for k, v in state.metrics.items():
            rich_console.print(f"  {k}: {v}")
