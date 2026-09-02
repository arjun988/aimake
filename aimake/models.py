"""Core data models for aimake."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ArtifactStatus(str, Enum):
    """Lifecycle status of an artifact in the build graph."""

    UNKNOWN = "unknown"
    UP_TO_DATE = "up_to_date"
    CHANGED = "changed"
    STALE = "stale"
    BUILDING = "building"
    SUCCESS = "success"
    FAILED = "failed"
    CACHED = "cached"


class BuildAction(str, Enum):
    """Planned action for an artifact during a build."""

    SKIP = "skip"
    RUN = "run"
    RESTORE = "restore"


@dataclass
class ArtifactState:
    """Persisted runtime state for a single artifact."""

    name: str
    fingerprint: str | None = None
    status: ArtifactStatus = ArtifactStatus.UNKNOWN
    created_at: datetime | None = None
    duration: float | None = None
    outputs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    command: str | None = None
    exit_code: int | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class BuildPlanEntry:
    """Single entry in a build plan."""

    name: str
    action: BuildAction
    status: ArtifactStatus
    reason: str = ""
    estimated_cost_usd: float | None = None
    estimated_tokens: int | None = None


@dataclass
class BuildPlan:
    """Complete build plan for a project."""

    entries: list[BuildPlanEntry] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)

    @property
    def to_run(self) -> list[str]:
        return [e.name for e in self.entries if e.action == BuildAction.RUN]

    @property
    def to_skip(self) -> list[str]:
        return [e.name for e in self.entries if e.action == BuildAction.SKIP]

    @property
    def to_restore(self) -> list[str]:
        return [e.name for e in self.entries if e.action == BuildAction.RESTORE]

    @property
    def estimated_total_cost_usd(self) -> float:
        return sum(
            e.estimated_cost_usd or 0.0
            for e in self.entries
            if e.action == BuildAction.RUN
        )

    @property
    def estimated_total_tokens(self) -> int:
        return sum(
            e.estimated_tokens or 0
            for e in self.entries
            if e.action == BuildAction.RUN
        )


@dataclass
class BuildResult:
    """Result of a completed build."""

    build_id: int
    success: bool
    duration: float
    rebuilt: list[str] = field(default_factory=list)
    reused: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    changed_artifacts: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    git_commit: str | None = None
    git_branch: str | None = None
    git_dirty: bool | None = None


@dataclass
class ExplainResult:
    """Explanation of why an artifact is stale."""

    target: str
    chain: list[str] = field(default_factory=list)
    root_cause: str = ""
    old_fingerprint: str | None = None
    new_fingerprint: str | None = None
    conclusion: str = ""


@dataclass
class ExecutionRecord:
    """Record of a command execution."""

    artifact: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    start_time: datetime
    end_time: datetime
    duration: float


@dataclass
class GitInfo:
    """Git repository metadata captured during a build."""

    commit: str | None = None
    branch: str | None = None
    dirty: bool | None = None
    available: bool = False
