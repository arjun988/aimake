"""Dataset artifact type."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aimake.artifacts.base import Artifact, ArtifactRegistry


@ArtifactRegistry.register
class DatasetArtifact(Artifact):
    artifact_type = "dataset"

    def collect_metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {"type": "dataset"}
        if not self.config.source:
            return meta

        path = self.project_root / self.config.source
        if not path.exists():
            meta["status"] = "missing"
            return meta

        meta["path"] = self.config.source
        meta["size_bytes"] = path.stat().st_size if path.is_file() else sum(
            f.stat().st_size for f in path.rglob("*") if f.is_file()
        )

        if path.is_file() and path.suffix == ".jsonl":
            try:
                with open(path, encoding="utf-8") as f:
                    meta["row_count"] = sum(1 for line in f if line.strip())
            except OSError:
                pass
        elif path.is_file() and path.suffix == ".json":
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    meta["row_count"] = len(data)
            except (OSError, json.JSONDecodeError):
                pass

        return meta
