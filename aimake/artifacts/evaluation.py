"""Evaluation artifact type."""

from __future__ import annotations

from typing import Any

from aimake.artifacts.base import Artifact, ArtifactRegistry


@ArtifactRegistry.register
class EvaluationArtifact(Artifact):
    artifact_type = "evaluation"

    def collect_metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {"type": "evaluation"}
        if self.config.metrics and self.config.metrics.file:
            meta["metrics_file"] = self.config.metrics.file
        return meta
