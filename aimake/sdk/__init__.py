"""Stable SDK surface for CI scripts and internal tools.

Prefer importing from here (or ``aimake``) instead of deep internal modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aimake.models import (
    ArtifactStatus,
    BuildAction,
    BuildPlan,
    BuildResult,
    ExplainResult,
)
from aimake.project import Project

__all__ = [
    "Aimake",
    "ArtifactStatus",
    "BuildAction",
    "BuildPlan",
    "BuildResult",
    "ExplainResult",
    "Project",
    "load",
]


def load(
    path: str | Path | None = None,
    *,
    project: str | None = None,
    debug: bool = False,
    verbose: bool = False,
) -> Project:
    """Load an aimake project.

    Parameters
    ----------
    path:
        Path to ``aimake.yaml`` (or directory containing it).
    project:
        Monorepo shorthand, e.g. ``apps/rag`` → ``apps/rag/aimake.yaml``.
    """
    if project and path:
        raise ValueError("Pass either path or project, not both")
    if project:
        from aimake.config.loader import resolve_project_config

        resolved = resolve_project_config(None, project)
        return Project.load(resolved, debug=debug, verbose=verbose)
    if path is not None:
        p = Path(path)
        if p.is_dir():
            p = p / "aimake.yaml"
        return Project.load(p, debug=debug, verbose=verbose)
    return Project.load(debug=debug, verbose=verbose)


class Aimake:
    """Thin ergonomic wrapper around :class:`Project` for scripts/CI.

    Example::

        from aimake.sdk import Aimake

        with Aimake.load("aimake.yaml") as ai:
            plan = ai.plan()
            result = ai.build()
            assert result.success
    """

    def __init__(self, project: Project) -> None:
        self._project = project

    @classmethod
    def load(cls, path: str | Path | None = None, **kwargs: Any) -> Aimake:
        return cls(load(path, **kwargs))

    @property
    def project(self) -> Project:
        return self._project

    def plan(self, targets: list[str] | None = None, **kwargs: Any) -> BuildPlan:
        return self._project.plan(targets, **kwargs)

    def status(self, targets: list[str] | None = None) -> dict[str, ArtifactStatus]:
        return self._project.status(targets)

    def build(self, targets: list[str] | None = None, **kwargs: Any) -> BuildResult:
        return self._project.build(targets, **kwargs)

    def explain(self, target: str, **kwargs: Any) -> ExplainResult:
        return self._project.explain(target, **kwargs)

    def doctor(self) -> list[str]:
        return self._project.doctor()

    def close(self) -> None:
        self._project.close()

    def __enter__(self) -> Aimake:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
