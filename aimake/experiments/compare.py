"""Compare builds and experiment trials."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aimake.state.database import StateDatabase


@dataclass
class MetricDelta:
    """Change in a single metric between two builds."""

    name: str
    baseline: float | None
    candidate: float | None
    delta: float | None
    improved: bool | None = None


@dataclass
class BuildComparison:
    """Comparison between two builds."""

    baseline_id: int
    candidate_id: int
    baseline_metrics: dict[str, Any] = field(default_factory=dict)
    candidate_metrics: dict[str, Any] = field(default_factory=dict)
    metric_deltas: list[MetricDelta] = field(default_factory=list)
    baseline_parameters: dict[str, Any] = field(default_factory=dict)
    candidate_parameters: dict[str, Any] = field(default_factory=dict)
    parameter_changes: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    baseline_git_commit: str | None = None
    candidate_git_commit: str | None = None
    baseline_rebuilt: list[str] = field(default_factory=list)
    candidate_rebuilt: list[str] = field(default_factory=list)

    @property
    def has_metric_changes(self) -> bool:
        return any(d.delta not in (None, 0) for d in self.metric_deltas)

    @property
    def summary(self) -> str:
        improved = [d for d in self.metric_deltas if d.improved]
        regressed = [d for d in self.metric_deltas if d.improved is False]
        parts = [f"Compared build #{self.baseline_id} → #{self.candidate_id}"]
        if improved:
            parts.append(f"{len(improved)} metric(s) improved")
        if regressed:
            parts.append(f"{len(regressed)} metric(s) regressed")
        if self.parameter_changes:
            parts.append(f"{len(self.parameter_changes)} parameter(s) changed")
        return "; ".join(parts)


class CompareEngine:
    """Compare metrics and parameters across builds."""

    def __init__(self, db: StateDatabase) -> None:
        self.db = db

    def resolve_build_ref(self, ref: str | int) -> int:
        """Resolve 'latest', 'previous', or numeric build ID."""
        if isinstance(ref, int):
            build = self.db.get_build(ref)
            if not build:
                raise ValueError(f"Build #{ref} not found")
            return ref

        ref_lower = str(ref).lower()
        if ref_lower == "latest":
            build_id = self.db.get_latest_build_id()
            if build_id is None:
                raise ValueError("No successful builds found")
            return build_id
        if ref_lower == "previous":
            latest = self.db.get_latest_build_id()
            build_id = self.db.get_previous_build_id(latest)
            if build_id is None:
                raise ValueError("No previous successful build found")
            return build_id

        try:
            build_id = int(ref)
        except ValueError as e:
            raise ValueError(
                f"Invalid build reference '{ref}'. Use a build ID, 'latest', or 'previous'."
            ) from e
        if not self.db.get_build(build_id):
            raise ValueError(f"Build #{build_id} not found")
        return build_id

    def compare(
        self,
        baseline: str | int,
        candidate: str | int,
        *,
        higher_is_better: set[str] | None = None,
        lower_is_better: set[str] | None = None,
    ) -> BuildComparison:
        baseline_id = self.resolve_build_ref(baseline)
        candidate_id = self.resolve_build_ref(candidate)
        if baseline_id == candidate_id:
            raise ValueError("Baseline and candidate builds must be different")

        baseline_build = self.db.get_build(baseline_id)
        candidate_build = self.db.get_build(candidate_id)
        assert baseline_build and candidate_build

        baseline_metrics = _numeric_metrics(baseline_build.get("metrics") or {})
        candidate_metrics = _numeric_metrics(candidate_build.get("metrics") or {})
        all_names = sorted(set(baseline_metrics) | set(candidate_metrics))

        higher = higher_is_better or set()
        lower = lower_is_better or set()

        deltas: list[MetricDelta] = []
        for name in all_names:
            base_val = baseline_metrics.get(name)
            cand_val = candidate_metrics.get(name)
            delta = None
            improved = None
            if base_val is not None and cand_val is not None:
                delta = round(cand_val - base_val, 6)
                if name in higher:
                    improved = delta > 0
                elif name in lower:
                    improved = delta < 0
            deltas.append(
                MetricDelta(
                    name=name,
                    baseline=base_val,
                    candidate=cand_val,
                    delta=delta,
                    improved=improved,
                )
            )

        base_params = baseline_build.get("parameters") or {}
        cand_params = candidate_build.get("parameters") or {}
        param_changes = {
            key: (base_params.get(key), cand_params.get(key))
            for key in sorted(set(base_params) | set(cand_params))
            if base_params.get(key) != cand_params.get(key)
        }

        return BuildComparison(
            baseline_id=baseline_id,
            candidate_id=candidate_id,
            baseline_metrics=baseline_metrics,
            candidate_metrics=candidate_metrics,
            metric_deltas=deltas,
            baseline_parameters=base_params,
            candidate_parameters=cand_params,
            parameter_changes=param_changes,
            baseline_git_commit=baseline_build.get("git_commit"),
            candidate_git_commit=candidate_build.get("git_commit"),
            baseline_rebuilt=baseline_build.get("rebuilt") or [],
            candidate_rebuilt=candidate_build.get("rebuilt") or [],
        )

    def compare_experiment_trials(
        self,
        experiment_id: int,
        *,
        best_only: bool = False,
    ) -> list[BuildComparison]:
        """Compare consecutive trials within an experiment."""
        experiment = self.db.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment #{experiment_id} not found")

        trials = self.db.get_experiment_trials(experiment_id)
        build_ids = [t["build_id"] for t in trials if t.get("build_id")]
        if len(build_ids) < 2:
            return []

        if best_only and experiment.get("best_build_id"):
            baseline_id = build_ids[0]
            return [
                self.compare(baseline_id, experiment["best_build_id"]),
            ]

        comparisons: list[BuildComparison] = []
        for left, right in zip(build_ids, build_ids[1:], strict=False):
            comparisons.append(self.compare(left, right))
        return comparisons


def _numeric_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    return {k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))}
