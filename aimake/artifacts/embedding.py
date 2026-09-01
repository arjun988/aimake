"""Embedding artifact type."""

from __future__ import annotations

import json
from typing import Any

from aimake.artifacts.base import Artifact, ArtifactRegistry


@ArtifactRegistry.register
class EmbeddingArtifact(Artifact):
    artifact_type = "embedding"

    def collect_metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {"type": "embedding"}
        for output in self.config.outputs:
            path = self.project_root / output
            if path.is_dir():
                for f in path.glob("*.json"):
                    try:
                        with open(f, encoding="utf-8") as fh:
                            data = json.load(fh)
                        if isinstance(data, list):
                            meta["embedding_count"] = len(data)
                            if data and "vector" in data[0]:
                                meta["dimension"] = len(data[0]["vector"])
                    except (OSError, json.JSONDecodeError):
                        pass
        return meta
