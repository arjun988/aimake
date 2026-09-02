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

_PROJECT_HELP = "Monorepo subproject path (e.g. apps/rag) containing aimake.yaml"


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
    from_source: Optional[str] = typer.Option(
        None,
        "--from",
        help="Generate from existing layout: makefile, dvc, prefect, airflow-dag",
    ),
) -> None:
    """Initialize a new aimake project."""
    from aimake.init.generators import supported_sources

    console.print_header()
    root = path or Path.cwd()
    try:
        config_path = Project.init(root, name=name, from_source=from_source)
    except (FileNotFoundError, ValueError) as e:
        console.print_error(str(e))
        if from_source:
            console.print_info(f"Supported --from values: {', '.join(supported_sources())}")
        raise typer.Exit(code=1)

    console.print_success(f"Created {config_path}")
    console.print_success(f"Created {root / '.aimake'}/")
    if not from_source:
        console.print_success(f"Created {root / 'build'}/")
    if from_source:
        console.print_info(f"\nGenerated aimake.yaml from [bold]{from_source}[/bold]")
        console.print_warning("Review generated commands before running builds.")
    else:
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
    project: Optional[str] = typer.Option(None, "--project", "-P", help=_PROJECT_HELP),
) -> None:
    """Build the dependency graph incrementally."""
    try:
        proj = _load_project(config, project=project, debug=debug, verbose=verbose)
        console.print_header()
        console.print_info("Loading project...")
        console.print_success("Configuration loaded")

        force_targets = set(targets or []) if force else set()
        if force and not targets:
            force_targets = set(proj.graph.names())

        console.print_info("\nBuilding dependency graph...")
        statuses = proj.status(targets)
        for name in proj.graph.names() if not targets else targets:
            if name in statuses:
                console.print(f"  {name:<25} {console.status_label(statuses[name])}")

        plan = proj.plan(targets, force=list(force_targets) if force else None)
        console.print_build_plan(plan)

        if dry_run:
            console.print("\n[bold]DRY RUN[/bold]\n")
            console.print("[bold]Would execute:[/bold]")
            for i, name in enumerate(plan.to_run, 1):
                console.print(f"  {i}. {name}")
            console.print("\n[bold]Would reuse:[/bold]")
            for name in plan.to_skip + plan.to_restore:
                console.print(f"  {name}")
            proj.close()
            return

        console.print("\n[bold]Executing...[/bold]\n")

        result = proj.build(
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
            from aimake.constants import LOGS_DIR

            if result.build_id:
                log_path = (
                    proj.project_root
                    / ".aimake"
                    / LOGS_DIR
                    / f"build-{result.build_id:03d}.log"
                )
                if log_path.is_file():
                    for line in log_path.read_text(encoding="utf-8").splitlines():
                        if line.startswith("FAILED "):
                            console.print_error(line)
            proj.close()
            raise typer.Exit(code=1)

        proj.close()

    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def plan(
    targets: Optional[list[str]] = typer.Argument(None, help="Specific targets"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-P", help=_PROJECT_HELP),
    debug: bool = typer.Option(False, "--debug"),
    format: str = typer.Option("text", "--format", "-f", help="Output: text or json"),
) -> None:
    """Show what would happen without executing."""
    try:
        proj = _load_project(config, project=project, debug=debug)
        plan_obj = proj.plan(targets)
        if format == "json":
            import json as _json

            payload = {
                "to_run": plan_obj.to_run,
                "to_skip": plan_obj.to_skip,
                "to_restore": plan_obj.to_restore,
                "estimated_total_cost_usd": plan_obj.estimated_total_cost_usd,
                "estimated_total_tokens": plan_obj.estimated_total_tokens,
                "entries": [
                    {
                        "name": e.name,
                        "action": e.action.value,
                        "status": e.status.value,
                        "reason": e.reason,
                        "estimated_cost_usd": e.estimated_cost_usd,
                        "estimated_tokens": e.estimated_tokens,
                    }
                    for e in plan_obj.entries
                ],
            }
            typer.echo(_json.dumps(payload, indent=2))
        else:
            console.print_build_plan(plan_obj)
        proj.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def status(
    targets: Optional[list[str]] = typer.Argument(None),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-P", help=_PROJECT_HELP),
) -> None:
    """Show artifact status."""
    try:
        project = _load_project(config, project=project)
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
    serve_ui: bool = typer.Option(False, "--serve", help="Start dashboard API for the web UI"),
    host: str = typer.Option("127.0.0.1", "--host", help="API host (with --serve)"),
    port: int = typer.Option(8765, "--port", "-p", help="API port (with --serve)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Display the dependency DAG."""
    try:
        project = _load_project(config)

        if serve_ui:
            from aimake.serve.api import run_server

            console.print_header("AIMAKE GRAPH / DASHBOARD API")
            console.print_success(f"Serving graph API on http://{host}:{port}")
            console.print_info("Open the Next.js dashboard (dashboard/) against this API.")
            server = run_server(project, host=host, port=port)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                console.print_info("\nStopped.")
                server.shutdown()
            finally:
                project.close()
            return

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
    tree: bool = typer.Option(False, "--tree", help="Show dependency tree with costs"),
    format: str = typer.Option("text", "--format", "-f", help="Output: text or json"),
) -> None:
    """Explain why a target is stale."""
    try:
        project = _load_project(config, debug=debug)
        result = project.explain(target, tree=tree or format == "json")

        if format == "json":
            payload = {
                "target": result.target,
                "chain": result.chain,
                "root_cause": result.root_cause,
                "conclusion": result.conclusion,
                "old_fingerprint": result.old_fingerprint,
                "new_fingerprint": result.new_fingerprint,
                "estimated_cost_usd": result.estimated_cost_usd,
                "estimated_tokens": result.estimated_tokens,
                "tree": [
                    {
                        "name": n.name,
                        "status": n.status,
                        "reason": n.reason,
                        "estimated_cost_usd": n.estimated_cost_usd,
                        "estimated_tokens": n.estimated_tokens,
                        "validation_errors": n.validation_errors,
                        "external_notes": n.external_notes,
                    }
                    for n in result.tree
                ],
            }
            typer.echo(json.dumps(payload, indent=2))
        else:
            console.print_explain(result, tree=tree)

        project.close()
    except (ConfigError, ValueError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),
    port: int = typer.Option(8765, "--port", "-p", help="API port"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    open_browser: bool = typer.Option(False, "--open", help="Open dashboard URL hint"),
) -> None:
    """Start the dashboard API server (pair with Next.js UI in dashboard/)."""
    from aimake.serve.api import run_server

    try:
        project = _load_project(config)
        console.print_header("AIMAKE DASHBOARD API")
        console.print_success(f"Listening on http://{host}:{port}")
        console.print_info("Endpoints: /api/overview /api/graph /api/builds /api/experiments /api/registry /api/cache")
        console.print_info("Frontend: cd dashboard && npm install && npm run dev")
        console.print_info(f"Set NEXT_PUBLIC_AIMAKE_API=http://{host}:{port}")
        if open_browser:
            import webbrowser

            webbrowser.open(f"http://localhost:3000")
        console.print_info("Press Ctrl+C to stop\n")
        server = run_server(project, host=host, port=port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            console.print_info("\nStopped.")
            server.shutdown()
        finally:
            project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def watch(
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    interval: float = typer.Option(2.0, "--interval", "-i", help="Poll interval (seconds)"),
    build: bool = typer.Option(False, "--build", "-b", help="Auto-build on change"),
) -> None:
    """Watch inputs and re-plan (optionally rebuild) when files change."""
    from aimake.watch import collect_watch_paths, watch as run_watch

    project = None
    try:
        project = _load_project(config)
        paths = collect_watch_paths(project.project_root, project.config)
        console.print_header("AIMAKE WATCH")
        console.print_info(f"Watching {len(paths)} path(s) every {interval}s")
        console.print_info("Press Ctrl+C to stop\n")

        def on_change() -> None:
            plan = project.plan()
            console.print("\n[bold yellow]Change detected[/bold yellow]")
            console.print_build_plan(plan)
            if not plan.to_run:
                console.print_success("Nothing to rebuild")

        run_watch(project, interval=interval, build=build, on_change=on_change)
    except KeyboardInterrupt:
        console.print_info("\nStopped.")
    except (ConfigError, ValueError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)
    finally:
        if project is not None:
            project.close()


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
def repro(
    format: str = typer.Option(
        "markdown", "--format", "-f", help="markdown | json | pdf"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-P", help=_PROJECT_HELP),
) -> None:
    """Generate a reproducibility report (env, fingerprints, drift, attestations)."""
    try:
        proj = _load_project(config, project=project)
        path = proj.repro_report(fmt=format.lower(), output=output)
        console.print_success(f"Wrote {path}")
        proj.close()
    except (ConfigError, ValueError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def lineage(
    formats: Optional[list[str]] = typer.Option(
        None, "--format", "-f", help="openlineage, mlflow, and/or wandb"
    ),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-P", help=_PROJECT_HELP),
) -> None:
    """Export pipeline lineage (OpenLineage / MLflow / W&B graph JSON)."""
    try:
        proj = _load_project(config, project=project)
        written = proj.export_lineage(formats=formats, output_dir=output_dir)
        if not written:
            console.print_warning("No lineage files written (check --format)")
        for fmt, path in written.items():
            console.print_success(f"{fmt}: {path}")
        proj.close()
    except (ConfigError, ValueError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def probe(
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-P", help=_PROJECT_HELP),
) -> None:
    """Probe external model/API deps for revision drift."""
    try:
        proj = _load_project(config, project=project)
        findings = proj.probe_external_drift()
        if not findings:
            console.print_info("No external deps with probe: true")
        drifted = False
        for f in findings:
            label = f"{f['artifact']}/{f['name']}"
            if not f.get("ok"):
                console.print_warning(f"{label}: probe failed — {f.get('detail')}")
            elif f.get("drifted"):
                drifted = True
                console.print_warning(
                    f"{label}: DRIFT pinned={f.get('pinned')} live={f.get('live')}"
                )
            else:
                console.print_success(f"{label}: ok ({f.get('live') or f.get('pinned')})")
        proj.close()
        if drifted:
            raise typer.Exit(code=2)
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
def diff(
    artifact: str = typer.Argument(..., help="Artifact to diff"),
    baseline: str = typer.Option("stored", "--baseline", "-b", help="Baseline: stored, lock, current"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show what changed in an artifact (dataset, model, prompt)."""
    try:
        project = _load_project(config)
        result = project.diff(artifact, baseline=baseline)
        console.print_diff(result)
        project.close()
    except (ConfigError, ValueError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


cache_app = typer.Typer(help="Remote cache management.")
app.add_typer(cache_app, name="cache")


@cache_app.command("status")
def cache_status(
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show local and remote cache status."""
    try:
        project = _load_project(config)
        status = project.cache_status()
        console.print_cache_status(status)
        project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@cache_app.command("push")
def cache_push(
    fingerprint: Optional[str] = typer.Argument(None, help="Specific fingerprint to push"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Push local cache entries to remote storage (S3)."""
    try:
        project = _load_project(config)
        if not project.config.cache.remote:
            console.print_error("Remote cache not configured in aimake.yaml")
            raise typer.Exit(code=1)
        pushed = project.cache_push(fingerprint)
        console.print_success(f"Pushed {len(pushed)} cache entry(s)")
        for fp in pushed:
            console.print_info(f"  {fp[:48]}...")
        project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@cache_app.command("pull")
def cache_pull(
    fingerprint: Optional[str] = typer.Argument(None, help="Specific fingerprint to pull"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Pull cache entries from remote storage (S3)."""
    try:
        project = _load_project(config)
        if not project.config.cache.remote:
            console.print_error("Remote cache not configured in aimake.yaml")
            raise typer.Exit(code=1)
        pulled = project.cache_pull(fingerprint)
        console.print_success(f"Pulled {len(pulled)} cache entry(s)")
        for fp in pulled:
            console.print_info(f"  {fp[:48]}...")
        project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@cache_app.command("sync")
def cache_sync(
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-P", help=_PROJECT_HELP),
) -> None:
    """Pull missing entries from remote, push new local entries."""
    try:
        proj = _load_project(config, project=project)
        if not proj.config.cache.remote:
            console.print_error("Remote cache not configured in aimake.yaml")
            raise typer.Exit(code=1)
        pulled = proj.cache_pull()
        pushed = proj.cache_push()
        console.print_success(f"Sync complete: {len(pulled)} pulled, {len(pushed)} pushed")
        proj.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@cache_app.command("remote-init")
def cache_remote_init(
    bucket: str = typer.Option(..., "--bucket", "-b", help="S3 bucket name"),
    prefix: str = typer.Option("aimake/cache/", "--prefix", help="Key prefix"),
    region: Optional[str] = typer.Option(None, "--region", "-r"),
    endpoint_url: Optional[str] = typer.Option(None, "--endpoint", help="S3-compatible endpoint"),
    team_id: Optional[str] = typer.Option(None, "--team", "-t", help="Shared org team id"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-P", help=_PROJECT_HELP),
) -> None:
    """Write shared team cache (S3) settings into aimake.yaml."""
    try:
        proj = _load_project(config, project=project)
        path = proj.cache_init_remote(
            bucket=bucket,
            prefix=prefix,
            region=region,
            endpoint_url=endpoint_url,
            team_id=team_id,
        )
        console.print_success(f"Wrote cache.remote to {path}")
        if team_id:
            console.print_info(f"Team prefix: {prefix.rstrip('/')}/{team_id}/")
        console.print_info("Commit aimake.lock after a successful build so CI/laptops share fingerprints.")
        console.print_info("Then: aimake cache pull-lock && aimake build")
        proj.close()
    except (ConfigError, ValueError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@cache_app.command("pull-lock")
def cache_pull_lock(
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-P", help=_PROJECT_HELP),
) -> None:
    """Pull fingerprints pinned in aimake.lock from the shared team cache."""
    try:
        proj = _load_project(config, project=project)
        if not proj.config.cache.remote:
            console.print_error("Remote cache not configured")
            raise typer.Exit(code=1)
        pulled = proj.cache_pull_lock()
        console.print_success(f"Pulled {len(pulled)} lock-pinned entr{'y' if len(pulled)==1 else 'ies'}")
        for fp in pulled[:20]:
            console.print_info(f"  {fp[:48]}...")
        proj.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def workers(
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show GPU and distributed worker status."""
    try:
        project = _load_project(config)
        status = project.workers_status()
        console.print_workers_status(status)
        project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def compare(
    baseline: str = typer.Argument("previous", help="Baseline build: ID, latest, or previous"),
    candidate: str = typer.Argument("latest", help="Candidate build: ID, latest, or previous"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Compare metrics between two builds."""
    try:
        project = _load_project(config)
        result = project.compare_builds(baseline, candidate)
        console.print_compare(result)
        project.close()
    except (ConfigError, ValueError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def optimize(
    trials: Optional[int] = typer.Option(None, "--trials", "-n", help="Number of trials"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show planned trials without building"),
    name: Optional[str] = typer.Option(None, "--name", help="Experiment name"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Run automatic hyperparameter optimization."""
    try:
        project = _load_project(config)
        result = project.optimize(trials=trials, dry_run=dry_run, name=name)
        console.print_optimization_result(result)
        project.close()
        if not dry_run and not result.success:
            raise typer.Exit(code=1)
    except (ConfigError, ValueError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


experiments_app = typer.Typer(help="Experiment tracking and comparison.")


@experiments_app.command("list")
def experiments_list(
    limit: int = typer.Option(20, "--limit", "-n"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """List optimization experiments."""
    try:
        project = _load_project(config)
        console.print_experiments(project.experiments(limit))
        project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@experiments_app.command("show")
def experiments_show(
    experiment_id: int = typer.Argument(..., help="Experiment ID"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show trials for an experiment."""
    try:
        project = _load_project(config)
        exp = project.cache.state_db.get_experiment(experiment_id)
        if not exp:
            console.print_error(f"Experiment #{experiment_id} not found")
            raise typer.Exit(code=1)
        trials = project.experiment_trials(experiment_id)
        console.print(f"\n[bold]Experiment #{experiment_id}[/bold]: {exp.get('name')}\n")
        for trial in trials:
            params = json.loads(trial["parameters"]) if isinstance(trial.get("parameters"), str) else trial.get("parameters", {})
            metrics = json.loads(trial["metrics"]) if isinstance(trial.get("metrics"), str) else trial.get("metrics", {})
            console.print(
                f"  Trial {trial['trial_number']}: "
                f"build=#{trial.get('build_id', '-')} "
                f"objective={trial.get('objective_value')} "
                f"params={params} metrics={metrics}"
            )
        project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


app.add_typer(experiments_app, name="experiments")


registry_app = typer.Typer(help="Versioned artifact registry.")


@registry_app.command("list")
def registry_list(
    artifact: Optional[str] = typer.Option(None, "--artifact", "-a"),
    stage: Optional[str] = typer.Option(None, "--stage", "-s"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t"),
    limit: int = typer.Option(50, "--limit", "-n"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """List registered artifact versions."""
    try:
        project = _load_project(config)
        entries = project.registry_list(artifact, stage=stage, tag=tag, limit=limit)
        console.print_registry(entries)
        project.close()
    except (ConfigError, ValueError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@registry_app.command("show")
def registry_show(
    artifact: str = typer.Argument(..., help="Artifact name"),
    version: str = typer.Argument(..., help="Version (e.g. v1)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show a registry entry."""
    try:
        project = _load_project(config)
        entry = project.registry.get(artifact, version)
        if not entry:
            console.print_error(f"Not found: {artifact}@{version}")
            raise typer.Exit(code=1)
        console.print(f"\n[bold]{entry.artifact_name}@{entry.version}[/bold]")
        console.print(f"  stage:       {entry.stage}")
        console.print(f"  fingerprint: {entry.fingerprint}")
        console.print(f"  build:       #{entry.build_id}" if entry.build_id else "  build:       -")
        if entry.tags:
            console.print(f"  tags:        {', '.join(entry.tags)}")
        if entry.metrics:
            console.print(f"  metrics:     {entry.metrics}")
        project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@registry_app.command("promote")
def registry_promote(
    artifact: str = typer.Argument(..., help="Artifact name"),
    version: str = typer.Argument(..., help="Version"),
    stage: str = typer.Option("production", "--stage", "-s"),
    force: bool = typer.Option(False, "--force", help="Skip policy gates"),
    no_push: bool = typer.Option(False, "--no-push", help="Skip remote registry push"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-P", help=_PROJECT_HELP),
) -> None:
    """Promote a registry version to staging or production (policy-gated)."""
    try:
        from aimake.policy import PolicyError

        proj = _load_project(config, project=project)
        entry, push_result = proj.registry_promote(
            artifact,
            version,
            stage,
            force=force,
            push=False if no_push else None,
        )
        console.print_success(f"Promoted {artifact}@{version} → {entry.stage}")
        if push_result:
            console.print_success(f"Pushed to {push_result.backend}: {push_result.uri}")
        proj.close()
    except PolicyError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)
    except (ConfigError, ValueError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@registry_app.command("push")
def registry_push_cmd(
    artifact: str = typer.Argument(..., help="Artifact name"),
    version: str = typer.Argument(..., help="Version"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-P", help=_PROJECT_HELP),
) -> None:
    """Push a registry version to remote (S3 / Hugging Face / W&B)."""
    try:
        from aimake.registry.remote import RegistryRemoteError

        proj = _load_project(config, project=project)
        result = proj.registry_push(artifact, version)
        console.print_success(f"Pushed {artifact}@{version} → {result.uri}")
        proj.close()
    except (ConfigError, ValueError, RegistryRemoteError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@registry_app.command("tag")
def registry_tag(
    artifact: str = typer.Argument(..., help="Artifact name"),
    version: str = typer.Argument(..., help="Version"),
    tags: list[str] = typer.Argument(..., help="Tags to add"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-P", help=_PROJECT_HELP),
) -> None:
    """Add tags to a registry version."""
    try:
        proj = _load_project(config, project=project)
        entry = proj.registry_tag(artifact, version, tags)
        console.print_success(f"Tagged {artifact}@{version}: {', '.join(entry.tags)}")
        proj.close()
    except (ConfigError, ValueError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


app.add_typer(registry_app, name="registry")


@app.command()
def schedule(
    cron: Optional[str] = typer.Argument(
        None, help='Cron expression, e.g. "0 6 * * *" (daily 06:00)'
    ),
    job: Optional[str] = typer.Option(None, "--job", "-j", help="Named job from schedule.jobs"),
    once: bool = typer.Option(False, "--once", help="Run on next match then exit"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show next fire time only"),
    targets: Optional[list[str]] = typer.Option(None, "--target", "-t", help="Build targets"),
    force: bool = typer.Option(False, "--force", "-f"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-P", help=_PROJECT_HELP),
) -> None:
    """Run builds on a cron schedule (or a named schedule.jobs entry)."""
    try:
        from aimake.schedule import CronError, CronSchedule, next_matches, run_schedule_loop

        proj = _load_project(config, project=project)
        expression = cron
        job_targets = list(targets or [])
        job_force = force

        if job:
            sched = proj.config.schedule
            if not sched or job not in sched.jobs:
                console.print_error(f"Unknown schedule job '{job}'")
                raise typer.Exit(code=1)
            j = sched.jobs[job]
            if not j.enabled:
                console.print_error(f"Schedule job '{job}' is disabled")
                raise typer.Exit(code=1)
            expression = j.cron
            if not job_targets:
                job_targets = list(j.targets)
            job_force = job_force or j.force

        if not expression:
            console.print_error('Provide a cron expression or --job name')
            raise typer.Exit(code=1)

        schedule_obj = CronSchedule.parse(expression)
        nxt = next_matches(schedule_obj)
        console.print_info(f"Cron: {expression}")
        console.print_info(f"Next run (UTC): {nxt.isoformat()}")
        if dry_run:
            proj.close()
            return

        def tick() -> None:
            console.print_info(f"\n[{CronSchedule.parse(expression).expression}] building...")
            result = proj.build(
                targets=job_targets or None,
                force=list(proj.graph.names()) if job_force else None,
            )
            console.print_build_summary(result)

        console.print_info("Press Ctrl+C to stop\n")
        try:
            run_schedule_loop(expression, tick, once=once)
        except KeyboardInterrupt:
            console.print_info("\nStopped")
        proj.close()
    except (ConfigError, CronError, ValueError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command("notify-test")
def notify_test(
    event: str = typer.Option("fail", "--event", "-e", help="fail|success|quality_gate|cost_spike"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-P", help=_PROJECT_HELP),
) -> None:
    """Send a test notification via configured Slack/Discord/email channels."""
    try:
        from aimake.notify import Notifier

        proj = _load_project(config, project=project)
        sent = Notifier(proj.config.notifications).notify(
            event,
            f"aimake notify-test ({event})",
            f"Test notification from {proj.config.project.name}",
            fields={"project": proj.config.project.name, "root": str(proj.project_root)},
        )
        if sent:
            console.print_success(f"Sent via: {', '.join(sent)}")
        else:
            console.print_warning(
                "No channels sent. Enable notifications.* and set webhook/SMTP env vars."
            )
        proj.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def secrets(
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-P", help=_PROJECT_HELP),
) -> None:
    """Show which secrets sources loaded (keys only, never values)."""
    try:
        from aimake.secrets import load_secrets

        proj = _load_project(config, project=project)
        summary = load_secrets(proj.project_root, proj.config.secrets)
        console.print_header("SECRETS")
        dotenv_keys = summary.get("dotenv") or []
        console.print(f"  .env keys: {len(dotenv_keys)}")
        for k in dotenv_keys[:30]:
            console.print_info(f"    {k}")
        for p in summary.get("providers") or []:
            if p.get("ok"):
                console.print_success(f"  {p['type']}: {len(p.get('keys') or [])} keys")
            else:
                console.print_error(f"  {p['type']}: {p.get('error')}")
        proj.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@app.command()
def plugins(
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """List enabled plugins."""
    try:
        project = _load_project(config)
        console.print_header("PLUGINS")
        installed = project.plugin_manager.plugins
        if installed:
            for plugin in installed:
                console.print_success(f"{plugin.name} v{plugin.version}")
        else:
            console.print_info("No plugins enabled.")

        console.print_info("\nBuilt-in integrations:")
        plugin_checks = (
            ("Hugging Face", "huggingface", "plugins.huggingface", "huggingface"),
            ("Weights & Biases", "wandb", "plugins.wandb", "wandb"),
            ("DVC", "dvc", "plugins.dvc", "dvc"),
            ("Docker", "docker", "plugins.docker", "docker"),
            ("Ollama", "ollama", "plugins.ollama", "ollama"),
            ("MLflow", "mlflow", "optimization.mlflow", None),
            ("Optuna", "optuna", "optimization", None),
            ("S3 cache", "s3", "cache.remote", None),
        )
        for name, extra, config_path, plugin_name in plugin_checks:
            enabled = False
            if plugin_name and any(p.name == plugin_name for p in installed):
                enabled = True
            elif config_path == "plugins.huggingface":
                cfg = project.config.plugins.huggingface
                enabled = cfg is not None and cfg.enabled
            elif config_path == "plugins.wandb":
                cfg = project.config.plugins.wandb
                enabled = cfg is not None and cfg.enabled
            elif config_path == "plugins.dvc":
                cfg = project.config.plugins.dvc
                enabled = cfg is not None and cfg.enabled
            elif config_path == "plugins.docker":
                cfg = project.config.plugins.docker
                enabled = cfg is not None and cfg.enabled
            elif config_path == "plugins.ollama":
                cfg = project.config.plugins.ollama
                enabled = cfg is not None and cfg.enabled
            elif config_path == "optimization.mlflow":
                enabled = project.config.optimization.mlflow.enabled
            elif config_path == "optimization":
                enabled = project.config.optimization.strategy in ("bayesian", "optuna")
            elif config_path == "cache.remote":
                enabled = project.config.cache.remote is not None
            mark = "+" if enabled else "-"
            install_hint = f"pip install aimake[{extra}]" if extra else "see README"
            console.print_info(f"  [{mark}] {name}  ({install_hint})  — {config_path}")
        project.close()
    except ConfigError as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


hf_app = typer.Typer(help="Hugging Face Hub integration.")


@hf_app.command("pull")
def hf_pull(
    artifact: str = typer.Argument(..., help="Artifact to pull from the Hub"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Download a model or dataset from Hugging Face Hub."""
    try:
        project = _load_project(config)
        path = project.hf_pull(artifact)
        console.print_success(f"Pulled {artifact} → {path}")
        project.close()
    except (ConfigError, ValueError, ImportError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@hf_app.command("push")
def hf_push(
    artifact: str = typer.Argument(..., help="Artifact to push to the Hub"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Upload an artifact to Hugging Face Hub."""
    try:
        project = _load_project(config)
        repo_id = project.hf_push(artifact)
        console.print_success(f"Pushed {artifact} → {repo_id}")
        project.close()
    except (ConfigError, ValueError, ImportError, FileNotFoundError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@hf_app.command("status")
def hf_status(
    artifact: Optional[str] = typer.Argument(None, help="Artifact name (optional)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show Hugging Face Hub linkage for artifacts."""
    try:
        project = _load_project(config)
        statuses = project.hf_status(artifact)
        if not statuses:
            console.print_info("No Hugging Face-linked artifacts found.")
        else:
            for name, info in statuses.items():
                console.print(f"\n[bold cyan]{name}[/bold cyan]")
                console.print(f"  repo:   {info.get('repo_id')}")
                console.print(f"  rev:    {info.get('revision')}")
                console.print(f"  type:   {info.get('repo_type')}")
                console.print(f"  local:  {info.get('local_path')} ({'exists' if info.get('local_exists') else 'missing'})")
        project.close()
    except (ConfigError, ValueError, ImportError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


app.add_typer(hf_app, name="hf")


wandb_app = typer.Typer(help="Weights & Biases integration.")


@wandb_app.command("sync")
def wandb_sync(
    artifact: str = typer.Argument(..., help="Artifact to log to W&B"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Log metrics and artifacts for an artifact to Weights & Biases."""
    try:
        project = _load_project(config)
        project.wandb_sync(artifact)
        console.print_success(f"Synced {artifact} to Weights & Biases")
        project.close()
    except (ConfigError, ValueError, ImportError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@wandb_app.command("status")
def wandb_status(
    artifact: Optional[str] = typer.Argument(None, help="Artifact name (optional)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show W&B linkage for artifacts."""
    try:
        project = _load_project(config)
        statuses = project.wandb_status(artifact)
        if not statuses:
            console.print_info("No W&B-linked artifacts found.")
        else:
            for name, info in statuses.items():
                console.print(f"\n[bold cyan]{name}[/bold cyan]")
                console.print(f"  project:  {info.get('project')}")
                console.print(f"  entity:   {info.get('entity')}")
                console.print(f"  metrics:  {info.get('log_metrics')}")
                console.print(f"  artifacts:{info.get('log_artifacts')}")
        project.close()
    except (ConfigError, ValueError, ImportError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


app.add_typer(wandb_app, name="wandb")


dvc_app = typer.Typer(help="DVC data versioning.")


@dvc_app.command("pull")
def dvc_pull(
    artifact: str = typer.Argument(..., help="Artifact to pull from DVC remote"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Pull DVC-tracked data for an artifact."""
    try:
        project = _load_project(config)
        path = project.dvc_pull(artifact)
        console.print_success(f"Pulled {artifact} ({path})")
        project.close()
    except (ConfigError, ValueError, ImportError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@dvc_app.command("push")
def dvc_push(
    artifact: str = typer.Argument(..., help="Artifact to push to DVC remote"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Push DVC-tracked data for an artifact."""
    try:
        project = _load_project(config)
        path = project.dvc_push(artifact)
        console.print_success(f"Pushed {artifact} ({path})")
        project.close()
    except (ConfigError, ValueError, ImportError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@dvc_app.command("status")
def dvc_status(
    artifact: Optional[str] = typer.Argument(None, help="Artifact name (optional)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show DVC linkage for artifacts."""
    try:
        project = _load_project(config)
        statuses = project.dvc_status(artifact)
        if not statuses:
            console.print_info("No DVC-linked artifacts found.")
        else:
            for name, info in statuses.items():
                console.print(f"\n[bold cyan]{name}[/bold cyan]")
                console.print(f"  path:    {info.get('path')}")
                console.print(f"  remote:  {info.get('remote')}")
                console.print(f"  local:   {'exists' if info.get('local_exists') else 'missing'}")
        project.close()
    except (ConfigError, ValueError, ImportError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


app.add_typer(dvc_app, name="dvc")


docker_app = typer.Typer(help="Docker container execution.")


@docker_app.command("build")
def docker_build(
    artifact: str = typer.Argument(..., help="Artifact whose Docker image to build"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Build the Docker image for an artifact."""
    try:
        project = _load_project(config)
        tag = project.docker_build(artifact)
        console.print_success(f"Built Docker image {tag} for {artifact}")
        project.close()
    except (ConfigError, ValueError, ImportError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@docker_app.command("status")
def docker_status(
    artifact: Optional[str] = typer.Argument(None, help="Artifact name (optional)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show Docker configuration for artifacts."""
    try:
        project = _load_project(config)
        statuses = project.docker_status(artifact)
        if not statuses:
            console.print_info("No Docker-linked artifacts found.")
        else:
            for name, info in statuses.items():
                console.print(f"\n[bold cyan]{name}[/bold cyan]")
                console.print(f"  image:      {info.get('image')}")
                console.print(f"  dockerfile: {info.get('dockerfile')}")
                exists = info.get("image_exists")
                if exists is not None:
                    console.print(f"  built:      {'yes' if exists else 'no'}")
        project.close()
    except (ConfigError, ValueError, ImportError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


app.add_typer(docker_app, name="docker")


ollama_app = typer.Typer(help="Ollama local LLM integration.")


@ollama_app.command("pull")
def ollama_pull(
    artifact: str = typer.Argument(..., help="Artifact whose Ollama model to pull"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Pull an Ollama model for an artifact."""
    try:
        project = _load_project(config)
        model = project.ollama_pull(artifact)
        console.print_success(f"Pulled {model} for {artifact}")
        project.close()
    except (ConfigError, ValueError, ImportError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


@ollama_app.command("status")
def ollama_status(
    artifact: Optional[str] = typer.Argument(None, help="Artifact name (optional)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Show Ollama model linkage for artifacts."""
    try:
        project = _load_project(config)
        statuses = project.ollama_status(artifact)
        if not statuses:
            console.print_info("No Ollama-linked artifacts found.")
        else:
            for name, info in statuses.items():
                console.print(f"\n[bold cyan]{name}[/bold cyan]")
                console.print(f"  model:  {info.get('model')}")
                console.print(f"  host:   {info.get('host')}")
                console.print(f"  local:  {'exists' if info.get('local_exists') else 'missing'}")
        project.close()
    except (ConfigError, ValueError, ImportError) as e:
        console.print_error(str(e))
        raise typer.Exit(code=1)


app.add_typer(ollama_app, name="ollama")


def _load_project(
    config: Path | None = None,
    *,
    project: str | None = None,
    debug: bool = False,
    verbose: bool = False,
) -> Project:
    from aimake.config.loader import resolve_project_config

    resolved = resolve_project_config(config, project)
    if resolved:
        return Project.load(resolved, debug=debug, verbose=verbose)
    return Project.load(debug=debug, verbose=verbose)


def run() -> None:
    """Entry point for console_scripts."""
    app()


if __name__ == "__main__":
    run()
