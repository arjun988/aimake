"""Model artifact type."""

from __future__ import annotations

import json
from typing import Any

from aimake.artifacts.base import Artifact, ArtifactRegistry


@ArtifactRegistry.register
class ModelArtifact(Artifact):
    artifact_type = "model"

    def collect_metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {"type": "model", "parameters": self.config.parameters}

        if self.config.source:
            path = self.project_root / self.config.source
            if path.is_file():
                meta["source"] = self.config.source
                meta["size_bytes"] = path.stat().st_size
                if path.suffix == ".json":
                    try:
                        with open(path, encoding="utf-8") as f:
                            meta["model_config"] = json.load(f)
                    except (OSError, json.JSONDecodeError):
                        pass
            else:
                meta["status"] = "missing"

        return meta
