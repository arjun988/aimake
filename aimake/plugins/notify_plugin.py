"""Notification plugin hooked into build lifecycle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aimake.config.schema import AimakeConfig
from aimake.notify import Notifier
from aimake.plugins.base import AimakePlugin


class NotifyPlugin(AimakePlugin):
    """Emit Slack / Discord / email on build outcomes."""

    name = "notifications"
    version = "1.0.0"

    def __init__(self, config: AimakeConfig, project_root: Path) -> None:
        self.config = config
        self.project_root = project_root
        self.notifier = Notifier(config.notifications)

    def on_build_finish(self, context: dict[str, Any]) -> None:
        result = context.get("result") or {}
        success = bool(result.get("success", context.get("success", True)))
        failed = result.get("failed") or context.get("failed") or []
        duration = result.get("duration") or context.get("duration")
        cost = context.get("estimated_cost_usd")
        metrics = result.get("metrics") or context.get("metrics") or {}
        project = self.config.project.name

        fields = {
            "project": project,
            "duration": f"{duration:.1f}s" if isinstance(duration, (int, float)) else duration,
            "failed": ", ".join(failed) if failed else "—",
        }

        if not success:
            self.notifier.notify(
                "fail",
                f"aimake build failed — {project}",
                f"Failed artifacts: {', '.join(failed) or 'unknown'}",
                fields=fields,
            )
        else:
            self.notifier.notify(
                "success",
                f"aimake build ok — {project}",
                "Build completed successfully",
                fields=fields,
            )

        # Quality gates
        gates = self.config.quality_gates
        if gates and metrics:
            from aimake.metrics.quality import QualityGateChecker

            failures = QualityGateChecker(self.config).check(
                {k: v for k, v in metrics.items() if isinstance(v, (int, float))}
            )
            if failures:
                self.notifier.notify(
                    "quality_gate",
                    f"Quality gate failed — {project}",
                    "\n".join(str(f) for f in failures),
                    fields=fields,
                )

        spike = self.config.policy.cost_spike_usd if self.config.policy else None
        if spike is not None and cost is not None and float(cost) > float(spike):
            self.notifier.notify(
                "cost_spike",
                f"Cost spike — {project}",
                f"Estimated/build cost ${float(cost):.4f} exceeded spike ${spike:.4f}",
                fields=fields,
            )
