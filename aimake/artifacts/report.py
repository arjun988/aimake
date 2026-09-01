"""Report artifact type."""

from __future__ import annotations

from typing import Any

from aimake.artifacts.base import Artifact, ArtifactRegistry


@ArtifactRegistry.register
class ReportArtifact(Artifact):
    artifact_type = "report"

    def collect_metadata(self) -> dict[str, Any]:
        return {"type": "report", **self.config.metadata}
