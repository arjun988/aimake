"""Build planning — determine what to run, skip, or restore."""

from __future__ import annotations

from aimake.graph.dag import Graph
from aimake.models import ArtifactStatus, BuildAction, BuildPlan, BuildPlanEntry


class Planner:
    """Compute build plans from artifact statuses."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph

    def plan(
        self,
        statuses: dict[str, ArtifactStatus],
        *,
        force: set[str] | None = None,
        dry_run: bool = False,
    ) -> BuildPlan:
        """Create a build plan from current artifact statuses."""
        force = force or set()
        entries: list[BuildPlanEntry] = []

        for node in self.graph:
            name = node.name
            status = statuses.get(name, ArtifactStatus.UNKNOWN)

            if name in force:
                action = BuildAction.RUN
                reason = "forced rebuild"
            elif status == ArtifactStatus.UP_TO_DATE:
                action = BuildAction.SKIP
                reason = "unchanged"
            elif status == ArtifactStatus.CACHED:
                action = BuildAction.RESTORE
                reason = "cache hit"
            elif status in (ArtifactStatus.CHANGED, ArtifactStatus.STALE, ArtifactStatus.UNKNOWN):
                action = BuildAction.RUN
                reason = status.value
            elif status == ArtifactStatus.FAILED:
                action = BuildAction.RUN
                reason = "previous failure"
            else:
                action = BuildAction.SKIP
                reason = "unchanged"

            entries.append(
                BuildPlanEntry(name=name, action=action, status=status, reason=reason)
            )

        return BuildPlan(entries=entries)

    def compute_statuses(
        self,
        fingerprints: dict[str, str],
        stored_fingerprints: dict[str, str],
        graph: Graph,
        *,
        outputs_exist: dict[str, bool] | None = None,
        outputs_valid: dict[str, bool] | None = None,
        cache_hits: dict[str, bool] | None = None,
        force: set[str] | None = None,
    ) -> dict[str, ArtifactStatus]:
        """Determine status for each artifact based on fingerprints."""
        force = force or set()
        outputs_exist = outputs_exist or {}
        outputs_valid = outputs_valid or {}
        cache_hits = cache_hits or {}
        statuses: dict[str, ArtifactStatus] = {}

        for node in graph:
            name = node.name
            current_fp = fingerprints.get(name)
            stored_fp = stored_fingerprints.get(name)

            if name in force:
                statuses[name] = ArtifactStatus.STALE
                continue

            # Check if any dependency is stale/changed/failed (not CACHED — restore is fine)
            dep_stale = any(
                statuses.get(dep)
                in (
                    ArtifactStatus.STALE,
                    ArtifactStatus.CHANGED,
                    ArtifactStatus.FAILED,
                    ArtifactStatus.UNKNOWN,
                )
                for dep in node.dependencies
            )

            if current_fp is None:
                statuses[name] = ArtifactStatus.UNKNOWN
            elif stored_fp is None:
                statuses[name] = ArtifactStatus.STALE
            elif current_fp != stored_fp:
                statuses[name] = ArtifactStatus.CHANGED
            elif not outputs_exist.get(name, True):
                # #23 — restore from cache when blobs exist instead of full rebuild
                if cache_hits.get(name):
                    statuses[name] = ArtifactStatus.CACHED
                else:
                    statuses[name] = ArtifactStatus.STALE
            elif outputs_valid.get(name) is False:
                statuses[name] = ArtifactStatus.STALE
            elif dep_stale:
                statuses[name] = ArtifactStatus.STALE
            else:
                statuses[name] = ArtifactStatus.UP_TO_DATE

        return statuses
