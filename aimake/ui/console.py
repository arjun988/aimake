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
        changed_raw = build.get("changed_artifacts") or "[]"
        if isinstance(changed_raw, list):
            changed = changed_raw
        else:
            changed = json.loads(changed_raw)
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


def print_diff(result) -> None:
    """Print artifact diff result."""
    from aimake.diff.engine import DiffResult

    rich_console.print(f"\n[bold]DIFF: {result.artifact}[/bold] ({result.artifact_type})\n")
    rich_console.print(f"Baseline: {result.baseline}")
    rich_console.print(f"Status: {'[yellow]CHANGED[/yellow]' if result.has_changes else '[green]UNCHANGED[/green]'}")
    rich_console.print(f"\n{result.summary}\n")

    if result.changes:
        rich_console.print("[bold]Changes:[/bold]")
        for change in result.changes:
            rich_console.print(f"  [cyan]{change.field}[/cyan]: {change.description}")
            if change.old_value is not None:
                rich_console.print(f"    old: {change.old_value}")
            if change.new_value is not None:
                rich_console.print(f"    new: {change.new_value}")

    if result.unified_diff:
        rich_console.print("\n[bold]Diff:[/bold]")
        rich_console.print(result.unified_diff)


def print_cache_status(status: dict) -> None:
    rich_console.print("\n[bold]CACHE STATUS[/bold]\n")
    if not status.get("enabled"):
        rich_console.print("Remote cache: [dim]disabled[/dim]")
        rich_console.print(f"Local entries: {status.get('local_entries', 'N/A')}")
        return
    rich_console.print(f"Remote type: {status.get('type')}")
    rich_console.print(f"Local entries:  {status.get('local_entries', 0)}")
    rich_console.print(f"Remote entries: {status.get('remote_entries', 0)}")
    synced = status.get("synced", [])
    only_local = status.get("only_local", [])
    only_remote = status.get("only_remote", [])
    if synced:
        rich_console.print(f"\n[green]Synced:[/green] {len(synced)} entries")
    if only_local:
        rich_console.print(f"[yellow]Local only:[/yellow] {len(only_local)} entries")
    if only_remote:
        rich_console.print(f"[cyan]Remote only:[/cyan] {len(only_remote)} entries")


def print_registry(entries) -> None:
    """Print artifact registry entries."""
    if not entries:
        print_info("Registry is empty.")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("Artifact")
    table.add_column("Version")
    table.add_column("Stage")
    table.add_column("Fingerprint")
    table.add_column("Build")
    table.add_column("Tags")
    for entry in entries:
        fp = entry.fingerprint[:16] + "..." if entry.fingerprint else "-"
        tags = ", ".join(entry.tags) if entry.tags else "-"
        table.add_row(
            entry.artifact_name,
            entry.version,
            entry.stage,
            fp,
            f"#{entry.build_id}" if entry.build_id else "-",
            tags,
        )
    rich_console.print(table)


def print_workers_status(status: dict) -> None:
    rich_console.print("\n[bold]WORKERS & GPUs[/bold]\n")
    gpus = status.get("gpus_detected", [])
    if gpus:
        for g in gpus:
            rich_console.print(f"  GPU {g['index']}: {g['name']} ({g.get('memory_mb', '?')} MB)")
    else:
        rich_console.print("  [dim]No GPUs detected[/dim]")
    rich_console.print(
        f"\nGPUs available: {status.get('gpus_available', 0)} / {status.get('gpus_total', 0)}"
    )
    if status.get("workers_enabled"):
        rich_console.print("\n[bold]Workers:[/bold]")
        for w in status.get("workers", []):
            rich_console.print(
                f"  {w['name']} ({w['host']}): "
                f"{w['active_jobs']}/{w['jobs']} jobs, "
                f"{w['gpus_in_use']}/{w['gpus']} GPUs"
            )
    else:
        rich_console.print("\n[dim]Distributed workers disabled[/dim]")


def print_compare(result) -> None:
    """Print build comparison table."""
    rich_console.print(
        f"\n[bold]BUILD COMPARISON[/bold]  "
        f"#{result.baseline_id} → #{result.candidate_id}\n"
    )
    rich_console.print(f"[dim]{result.summary}[/dim]\n")

    if result.parameter_changes:
        rich_console.print("[bold]Parameters[/bold]")
        for name, (old, new) in result.parameter_changes.items():
            rich_console.print(f"  {name}: {old} → {new}")
        rich_console.print()

    if result.metric_deltas:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Metric")
        table.add_column("Baseline")
        table.add_column("Candidate")
        table.add_column("Delta")
        table.add_column("Trend")

        for delta in result.metric_deltas:
            trend = ""
            if delta.improved is True:
                trend = "[green]better[/green]"
            elif delta.improved is False:
                trend = "[red]worse[/red]"
            table.add_row(
                delta.name,
                _fmt_num(delta.baseline),
                _fmt_num(delta.candidate),
                _fmt_delta(delta.delta),
                trend,
            )
        rich_console.print(table)

    if result.baseline_git_commit or result.candidate_git_commit:
        rich_console.print(
            f"\nGit: {result.baseline_git_commit or '?'} → {result.candidate_git_commit or '?'}"
        )


def print_optimization_result(result) -> None:
    """Print optimization summary."""
    rich_console.print(f"\n[bold]OPTIMIZATION[/bold]  experiment #{result.experiment_id}\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Trial")
    table.add_column("Parameters")
    table.add_column("Objective")
    table.add_column("Build")
    table.add_column("Status")

    for trial in result.trials:
        params = ", ".join(f"{k}={v}" for k, v in trial.parameters.items())
        table.add_row(
            str(trial.trial_number),
            params or "-",
            _fmt_num(trial.objective_value),
            f"#{trial.build_id}" if trial.build_id else "-",
            "ok" if trial.success else "failed",
        )
    rich_console.print(table)

    if result.best_trial:
        rich_console.print(
            f"\n[green]Best trial #{result.best_trial.trial_number}[/green]: "
            f"objective={_fmt_num(result.best_value)} "
            f"build=#{result.best_build_id}"
        )
        if result.best_parameters:
            params = ", ".join(f"{k}={v}" for k, v in result.best_parameters.items())
            rich_console.print(f"Parameters: {params}")
    elif result.pareto_front:
        rich_console.print(f"\n[green]Pareto front: {len(result.pareto_front)} trial(s)[/green]")
        for trial in result.pareto_front:
            objs = ", ".join(
                f"{k}={_fmt_num(v)}" for k, v in trial.objective_values.items()
            )
            rich_console.print(f"  Trial #{trial.trial_number}: {objs}")
    elif not all(t.build_id is None for t in result.trials):
        print_warning("No successful trials with objective values")

    if result.stopped_early:
        print_info("Stopped early (no improvement within patience window)")
    if result.pruned_trials:
        print_info(f"Pruned trials: {result.pruned_trials}")
    if result.mlflow_run_id:
        print_info(f"MLflow run: {result.mlflow_run_id}")


def print_experiments(experiments: list[dict]) -> None:
    """Print experiment list."""
    if not experiments:
        print_info("No experiments yet. Run 'aimake optimize'.")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Objective")
    table.add_column("Best")
    table.add_column("Status")

    for exp in experiments:
        objective = f"{exp.get('objective_metric')} ({exp.get('objective_direction')})"
        table.add_row(
            str(exp["id"]),
            exp.get("name", ""),
            objective,
            _fmt_num(exp.get("best_value")),
            str(exp.get("status", "")),
        )
    rich_console.print(table)


def _fmt_num(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _fmt_delta(value) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.4g}"
