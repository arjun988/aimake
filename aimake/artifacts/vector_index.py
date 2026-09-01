"""Vector index artifact type."""

from __future__ import annotations

import json
from typing import Any

from aimake.artifacts.base import Artifact, ArtifactRegistry


@ArtifactRegistry.register
class VectorIndexArtifact(Artifact):
    artifact_type = "vector_index"

    def collect_metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {"type": "vector_index"}
        for output in self.config.outputs:
            path = self.project_root / output
            if path.is_dir():
                for f in path.glob("*.json"):
                    try:
                        with open(f, encoding="utf-8") as fh:
                            data = json.load(fh)
                        if isinstance(data, dict):
                            meta.update({
                                k: data[k]
                                for k in ("dimension", "count", "ids")
                                if k in data
                            })
                    except (OSError, json.JSONDecodeError):
                        pass
        return meta
