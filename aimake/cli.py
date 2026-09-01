"""aimake CLI — Typer-based command-line interface."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from aimake import __version__
from aimake.config.loader import ConfigError
from aimake.models import ArtifactStatus, BuildAction
from aimake.project import Project
from aimake.ui import console


def _configure_stdout() -> None:
    """Use UTF-8 on Windows so Rich can render symbols."""
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                try:
                    reconfigure(encoding="utf-8")
                except Exception:
                    pass


_configure_stdout()

app = typer.Typer(
    name="aimake",
    help="Incremental build system for AI applications.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aimake {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True
    ),
) -> None:
    """aimake — incremental build system for AI applications."""


@app.command()
def init(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Project directory"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Project name"),
) -> None:
    """Initialize a new aimake project."""
    console.print_header()
    root = path or Path.cwd()
    config_path = Project.init(root, name=name)
    console.print_success(f"Created {config_path}")
    console.print_success(f"Created {root / '.aimake'}/")
    console.print_success(f"Created {root / 'build'}/")
    console.print_info("\nReview aimake.yaml before running builds.")
    console.print_info("aimake.yaml contains executable commands.")
    console.print_info("\nNext steps:")
    console.print_info("  aimake plan")
    console.print_info("  aimake build")


@app.command()
def build(
    targets: Optional[list[str]] = typer.Argument(None, help="Specific targets to build"),
    force: bool = typer.Option(False, "--force", "-f", help="Force rebuild"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show plan without executing"),
    jobs: int = typer.Option(0, "--jobs", "-j", help="Parallel jobs (0 = auto)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    debug: bool = typer.Option(False, "--debug", help="Debug output"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Build the dependency graph incrementally."""
    try:
        project = _load_project(config, debug=debug, verbose=verbose)
        console.print_header()
        console.print_info("Loading project...")
        console.print_success("Configuration loaded")

        force_targets = set(targets or []) if force else set()
        if force and not targets:
            force_targets = set(project.graph.names())

        console.print_info("\nBuilding dependency graph...")
        statuses = project.status(targets)
        for name in project.graph.names() if not targets else targets:
            if name in statuses:
                console.print(f"  {name:<25} {console.status_label(statuses[name])}")

        plan = project.plan(targets, force=list(force_targets) if force else None)
        console.print_build_plan(plan)

        if dry_run:
            console.print("\n[bold]DRY RUN[/bold]\n")
            console.print("[bold]Would execute:[/bold]")
            for i, name in enumerate(plan.to_run, 1):
                console.print(f"  {i}. {name}")
            console.print("\n[bold]Would reuse:[/bold]")
            for name in plan.to_skip + plan.to_restore:
                console.print(f"  {name}")
            project.close()
            return

        console.print("\n[bold]Executing...[/bold]\n")

        def on_start(name: str) -> None:
            pass

        def on_complete(result) -> None:
            if result.success:
                console.print_success(result.name)
            else:
                console.print_error(f"{result.name}: {result.error}")

        result = project.build(
            targets=targets,
            force=list(force_targets) if force else None,
            jobs=jobs if jobs > 0 else None,
        )

        console.print_build_summary(result)

        if result.metrics:
            console.print_metrics(result.metrics)

        if not result.success:
            if result.failed:
                console.print_error(f"\nBuild failed on: {', '.join(result.failed)}")
            # Surface per-artifact errors from the build log when available
            from aimake.constants import LOGS_DIR
            if result.build_id:
                log_path = project.project_root / ".aimake" / LOGS_DIR / f"build-{result.build_id:03d}.log"
                if log_path.is_file():
                    for line in log_path.read_text(encoding="utf-8").splitlines():
                        if line.startswith("FAILED "):
                            console.print_error(line)
            project.close()
            raise typer.Exit(code=1)

        project.close()

    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def plan(
    targets: Optional[list[str]] = typer.Argument(None, help="Specific targets"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    """Show what would happen without executing."""
    try:
        project = _load_project(config, debug=debug)
        console.print_header("BUILD PLAN")
        console.print()

        plan = project.plan(targets)
        for entry in plan.entries:
            if entry.action == BuildAction.SKIP:
                symbol = console.SYMBOL_CACHED
            elif entry.action == BuildAction.RUN:
                symbol = console.SYMBOL_REBUILD
            else:
                symbol = console.SYMBOL_RESTORE
            console.print(f"  {entry.name:<20} {symbol}")

        project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def status(
    targets: Optional[list[str]] = typer.Argument(None),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show artifact status."""
    try:
        project = _load_project(config)
        console.print_header("AIMAKE STATUS")
        console.print()

        statuses = project.status(targets)
        names = project.graph.names() if not targets else targets
        for name in names:
            s = statuses.get(name, ArtifactStatus.UNKNOWN)
            label = {
                ArtifactStatus.UP_TO_DATE: "UP TO DATE",
                ArtifactStatus.CACHED: "UP TO DATE",
                ArtifactStatus.CHANGED: "CHANGED",
                ArtifactStatus.STALE: "STALE",
            }.get(s, s.value.upper())
            color = "green" if s in (ArtifactStatus.UP_TO_DATE, ArtifactStatus.CACHED) else (
                "yellow" if s == ArtifactStatus.CHANGED else "red"
            )
            console.print(f"  {name:<20} [{color}]{label}[/{color}]")

        project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def graph(
    format: str = typer.Option("ascii", "--format", "-f", help="Output format: ascii, json, dot"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Display the dependency DAG."""
    try:
        project = _load_project(config)

        if format == "json":
            typer.echo(json.dumps(project.graph_dict(), indent=2))
        elif format == "dot":
            typer.echo(project.graph_dot())
        else:
            console.print_header()
            console.print_graph_ascii(project.graph)

        project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def clean(
    all: bool = typer.Option(False, "--all", help="Clear local cache too"),
    targets: Optional[list[str]] = typer.Argument(None),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Remove generated build artifacts."""
    try:
        project = _load_project(config)
        removed = project.clean(all_cache=all, targets=targets)
        if removed:
            console.print_success(f"Removed {len(removed)} output(s)")
        else:
            console.print_info("Nothing to clean")
        if all:
            console.print_success("Cache cleared")
        project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def history(
    limit: int = typer.Option(20, "--limit", "-n"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show previous builds."""
    try:
        project = _load_project(config)
        builds = project.history(limit)
        if builds:
            console.print_history_table(builds)
        else:
            console.print_info("No build history yet")
        project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def inspect(
    artifact: str = typer.Argument(..., help="Artifact name"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Inspect an artifact."""
    try:
        project = _load_project(config)
        info = project.inspect(artifact)

        def fmt_size(n: int) -> str:
            for unit in ("B", "KB", "MB", "GB"):
                if n < 1024:
                    return f"{n:.1f} {unit}"
                n /= 1024
            return f"{n:.1f} TB"

        console.print_inspect(
            info["name"],
            type("State", (), {"status": info["status"], "created_at": info["created_at"],
                                "fingerprint": info["fingerprint"], "duration": info["duration"],
                                "metrics": info["metrics"]})(),
            info["type"],
            dependencies=info["dependencies"],
            files=info["files"],
        )
        if info["size_bytes"]:
            console.print(f"\nSize:\n  {fmt_size(info['size_bytes'])}")

        project.close()
    except (ConfigError, ValueError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def explain(
    target: str = typer.Argument(..., help="Target artifact"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    """Explain why a target is stale."""
    try:
        project = _load_project(config, debug=debug)
        result = project.explain(target)
        console.print_explain(result)
        project.close()
    except (ConfigError, ValueError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def doctor(
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Check project health."""
    try:
        project = _load_project(config)
        console.print_header("AIMAKE DOCTOR")
        console.print()

        issues = project.doctor()
        has_error = False
        for issue in issues:
            if issue.startswith("ERROR"):
                console.print_error(issue)
                has_error = True
            elif issue.startswith("WARNING"):
                console.print_warning(issue)
            elif issue.startswith("OK"):
                console.print_success(issue)
            else:
                console.print_info(issue)

        project.close()
        if has_error:
            raise typer.Exit(code=1)
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def eval(
    check: bool = typer.Option(False, "--check", help="Check quality gates"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Run evaluation quality gate checks."""
    try:
        project = _load_project(config)

        if check:
            from aimake.metrics.parser import MetricsParser

            parser = MetricsParser(project.project_root)
            all_metrics: dict = {}

            for name, artifact in project.config.artifacts.items():
                if artifact.metrics and artifact.metrics.file:
                    metrics = parser.parse_file(artifact.metrics.file)
                    all_metrics.update(metrics)

            if not all_metrics:
                console.print_warning("No metrics found. Run 'aimake build' first.")
                project.close()
                return

            failures = project.check_quality_gates(all_metrics)
            if failures:
                console.print("\n[bold red]QUALITY GATE FAILED[/bold red]\n")
                for f in failures:
                    console.print_error(str(f))
                project.close()
                raise typer.Exit(code=1)
            else:
                console.print_success("All quality gates passed")
                console.print_metrics(all_metrics)
        else:
            console.print_info("Use --check to evaluate quality gates")

        project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def logs(
    build_id: int = typer.Argument(..., help="Build ID"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show logs for a build."""
    try:
        project = _load_project(config)
        from aimake.constants import LOGS_DIR

        log_path = project.project_root / ".aimake" / LOGS_DIR / f"build-{build_id:03d}.log"
        if log_path.is_file():
            typer.echo(log_path.read_text(encoding="utf-8"))
        else:
            console.print_error(f"Log file not found: {log_path}")
            raise typer.Exit(code=1)
        project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def plugins() -> None:
    """List available plugins (future integrations)."""
    console.print_header("PLUGINS")
    console.print_info("No plugins installed.")
    console.print_info("\nFuture integrations:")
    for name in ("Hugging Face", "MLflow", "Weights & Biases", "DVC", "Docker", "Ollama"):
        console.print_info(f"  • {name}")


def _load_project(
    config: Path | None = None,
    *,
    debug: bool = False,
    verbose: bool = False,
) -> Project:
    if config:
        return Project.load(config, debug=debug, verbose=verbose)
    return Project.load(debug=debug, verbose=verbose)


def run() -> None:
    """Entry point for console_scripts."""
    app()


if __name__ == "__main__":
    run()
