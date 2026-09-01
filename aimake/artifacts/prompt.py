"""Prompt artifact type."""

from __future__ import annotations

from typing import Any

from aimake.artifacts.base import Artifact, ArtifactRegistry
from aimake.hashing.files import hash_string


@ArtifactRegistry.register
class PromptArtifact(Artifact):
    artifact_type = "prompt"

    def collect_metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {"type": "prompt"}
        if not self.config.source:
            return meta

        path = self.project_root / self.config.source
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            meta["source"] = self.config.source
            meta["char_count"] = len(content)
            meta["line_count"] = content.count("\n") + 1
            meta["content_hash"] = hash_string(content)
        else:
            meta["status"] = "missing"

        return meta
