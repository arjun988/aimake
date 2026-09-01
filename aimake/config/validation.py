"""Configuration validation utilities."""

from __future__ import annotations

from pathlib import Path

from aimake.config.schema import AimakeConfig, ArtifactConfig
from aimake.graph.dag import Graph, GraphError


class ValidationIssue:
    """A single validation issue."""

    def __init__(self, level: str, message: str, artifact: str | None = None) -> None:
        self.level = level  # error, warning
        self.message = message
        self.artifact = artifact

    def __str__(self) -> str:
        prefix = f"[{self.artifact}] " if self.artifact else ""
        return f"{self.level.upper()}: {prefix}{self.message}"


def validate_graph(config: AimakeConfig) -> list[ValidationIssue]:
    """Validate dependency graph structure."""
    issues: list[ValidationIssue] = []
    try:
        Graph.from_config(config)
    except GraphError as e:
        issues.append(ValidationIssue("error", str(e)))
    return issues


def validate_files(
    config: AimakeConfig,
    project_root: Path,
) -> list[ValidationIssue]:
    """Check that declared source and input files exist."""
    issues: list[ValidationIssue] = []
    for name, artifact in config.artifacts.items():
        if artifact.source:
            source = project_root / artifact.source
            if not source.exists():
                issues.append(
                    ValidationIssue(
                        "warning",
                        f"Source file not found: {artifact.source}",
                        name,
                    )
                )
        for inp in artifact.inputs:
            path = project_root / inp.replace("/**", "").replace("**", "")
            if not path.exists() and "**" not in inp:
                issues.append(
                    ValidationIssue(
                        "warning",
                        f"Input not found: {inp}",
                        name,
                    )
                )
    return issues


def validate_commands(config: AimakeConfig) -> list[ValidationIssue]:
    """Validate that active artifacts have commands and outputs."""
    issues: list[ValidationIssue] = []
    for name, artifact in config.artifacts.items():
        if artifact.command and not artifact.outputs:
            issues.append(
                ValidationIssue(
                    "warning",
                    "Active artifact has command but no declared outputs",
                    name,
                )
            )
    return issues


def validate_config(
    config: AimakeConfig,
    project_root: Path,
) -> list[ValidationIssue]:
    """Run all configuration validations."""
    issues: list[ValidationIssue] = []
    issues.extend(validate_graph(config))
    issues.extend(validate_files(config, project_root))
    issues.extend(validate_commands(config))
    return issues
