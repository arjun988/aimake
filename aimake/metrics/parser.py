"""Parse evaluation metrics from result files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MetricsParser:
    """Parse metrics from JSON result files."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def parse_file(self, relative_path: str) -> dict[str, Any]:
        """Parse metrics from a JSON file."""
        path = self.project_root / relative_path
        if not path.is_file():
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if isinstance(v, (int, float, str, bool))}
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def find_evaluation_metrics(
        self,
        artifacts: dict[str, Any],
        project_root: Path,
    ) -> dict[str, Any]:
        """Find and parse metrics from all evaluation artifacts."""
        all_metrics: dict[str, Any] = {}
        for name, config in artifacts.items():
            if hasattr(config, "metrics") and config.metrics and config.metrics.file:
                metrics = self.parse_file(config.metrics.file)
                if metrics:
                    all_metrics[name] = metrics
                    all_metrics.update(metrics)
        return all_metrics
