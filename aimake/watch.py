"""Watch project inputs and trigger incremental builds."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from aimake.config.schema import AimakeConfig
from aimake.project import Project


def collect_watch_paths(project_root: Path, config: AimakeConfig) -> list[Path]:
    """Paths that should trigger replanning when modified."""
    paths: set[Path] = set()
    paths.add(project_root / "aimake.yaml")

    for artifact in config.artifacts.values():
        if artifact.source:
            p = project_root / artifact.source
            if p.exists():
                paths.add(p if p.is_file() else p)
        for inp in artifact.inputs:
            for match in project_root.glob(inp):
                if match.exists():
                    paths.add(match if match.is_dir() else match.parent)
        for out in artifact.outputs:
            p = project_root / out
            if p.exists():
                paths.add(p if p.is_file() else p)

    return sorted(paths)


def snapshot_mtimes(paths: list[Path]) -> dict[str, float]:
    mtimes: dict[str, float] = {}
    for path in paths:
        try:
            if path.is_file():
                mtimes[str(path)] = path.stat().st_mtime
            elif path.is_dir():
                mtimes[str(path)] = max(
                    (p.stat().st_mtime for p in path.rglob("*") if p.is_file()),
                    default=path.stat().st_mtime,
                )
        except OSError:
            continue
    return mtimes


def watch(
    project: Project,
    *,
    interval: float = 2.0,
    build: bool = False,
    on_change: Callable[[], None] | None = None,
) -> None:
    """Poll watch paths; run plan (and optional build) when files change."""
    paths = collect_watch_paths(project.project_root, project.config)
    if not paths:
        raise ValueError("No watch paths found in project configuration")

    last = snapshot_mtimes(paths)
    if on_change:
        on_change()

    while True:
        time.sleep(interval)
        current = snapshot_mtimes(paths)
        if current == last:
            continue
        last = current

        if on_change:
            on_change()

        plan = project.plan()
        if build and plan.to_run:
            project.build()
