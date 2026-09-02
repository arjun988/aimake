"""Quality gate evaluation for CI."""

from __future__ import annotations

from dataclasses import dataclass

from aimake.config.schema import AimakeConfig, QualityGateConfig


@dataclass
class QualityGateFailure:
    """A single quality gate failure."""

    metric: str
    value: float
    threshold: float
    comparison: str  # "minimum", "maximum", or "required"

    def __str__(self) -> str:
        if self.comparison == "required":
            return f"{self.metric}:\n  missing (required by quality_gates)"
        op = "<" if self.comparison == "minimum" else ">"
        req = "required" if self.comparison == "minimum" else "maximum"
        return f"{self.metric}:\n  {self.value} {op} {req} {self.threshold}"


class QualityGateChecker:
    """Check metrics against configured quality gates."""

    def __init__(self, config: AimakeConfig) -> None:
        self.gates = config.quality_gates

    def check(self, metrics: dict[str, float | int]) -> list[QualityGateFailure]:
        """Evaluate metrics against all quality gates."""
        failures: list[QualityGateFailure] = []

        for metric_name, gate in self.gates.items():
            if metric_name not in metrics:
                if gate.required:
                    failures.append(
                        QualityGateFailure(
                            metric=metric_name,
                            value=float("nan"),
                            threshold=gate.minimum or gate.maximum or 0.0,
                            comparison="required",
                        )
                    )
                continue
            value = float(metrics[metric_name])
            failure = self._check_gate(metric_name, value, gate)
            if failure:
                failures.append(failure)

        return failures

    def _check_gate(
        self,
        name: str,
        value: float,
        gate: QualityGateConfig,
    ) -> QualityGateFailure | None:
        if gate.minimum is not None and value < gate.minimum:
            return QualityGateFailure(
                metric=name,
                value=value,
                threshold=gate.minimum,
                comparison="minimum",
            )
        if gate.maximum is not None and value > gate.maximum:
            return QualityGateFailure(
                metric=name,
                value=value,
                threshold=gate.maximum,
                comparison="maximum",
            )
        return None
