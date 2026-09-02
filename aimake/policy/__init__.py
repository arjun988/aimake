"""Promote policy / approval gates."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from aimake.config.schema import AimakeConfig, PromotePolicyConfig


@dataclass
class PolicyViolation:
    """A single policy gate failure."""

    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class PolicyError(Exception):
    """Raised when promote is blocked by policy."""

    def __init__(self, violations: list[PolicyViolation]) -> None:
        self.violations = violations
        super().__init__(
            "Policy blocked promote:\n" + "\n".join(f"  - {v}" for v in violations)
        )


class PromotePolicyChecker:
    """Enforce promote gates (metrics, cost, tags, approval env)."""

    def __init__(self, config: AimakeConfig) -> None:
        self.config = config
        self.policy = config.policy.promote if config.policy else None

    def check(
        self,
        *,
        stage: str,
        metrics: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        cost_usd: float | None = None,
        force: bool = False,
    ) -> list[PolicyViolation]:
        if force or self.policy is None:
            return []

        policy: PromotePolicyConfig = self.policy
        stage_l = stage.lower()
        gated = {s.lower() for s in policy.stages}
        if stage_l not in gated:
            return []

        violations: list[PolicyViolation] = []
        metrics = metrics or {}
        tags = tags or []

        for name, gate in policy.metrics.items():
            if name not in metrics:
                if gate.required:
                    violations.append(
                        PolicyViolation("metric", f"{name}: missing (required)")
                    )
                continue
            value = metrics[name]
            if not isinstance(value, (int, float)):
                continue
            if gate.minimum is not None and float(value) < gate.minimum:
                violations.append(
                    PolicyViolation(
                        "metric",
                        f"{name}: {value} < minimum {gate.minimum}",
                    )
                )
            if gate.maximum is not None and float(value) > gate.maximum:
                violations.append(
                    PolicyViolation(
                        "metric",
                        f"{name}: {value} > maximum {gate.maximum}",
                    )
                )

        if policy.max_cost_usd is not None and cost_usd is not None:
            if cost_usd > policy.max_cost_usd:
                violations.append(
                    PolicyViolation(
                        "cost",
                        f"cost ${cost_usd:.4f} exceeds max_cost_usd ${policy.max_cost_usd:.4f}",
                    )
                )

        if policy.require_tag and policy.require_tag not in tags:
            violations.append(
                PolicyViolation(
                    "tag",
                    f"required tag '{policy.require_tag}' missing (have: {tags or 'none'})",
                )
            )

        if policy.require_approval_env:
            env_name = policy.require_approval_env
            if os.environ.get(env_name, "").strip() not in (
                "1",
                "true",
                "yes",
                "TRUE",
                "YES",
            ):
                violations.append(
                    PolicyViolation(
                        "approval",
                        f"set {env_name}=1 to approve promote to {stage_l}",
                    )
                )

        return violations

    def enforce(self, **kwargs: Any) -> None:
        violations = self.check(**kwargs)
        if violations:
            raise PolicyError(violations)
