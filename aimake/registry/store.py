"""Persistent artifact registry with stages and tags."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from aimake.state.database import StateDatabase

STAGES = ("dev", "staging", "production")


@dataclass
class RegistryEntry:
    """A versioned artifact in the registry."""

    id: int
    artifact_name: str
    version: str
    fingerprint: str
    build_id: int | None
    stage: str
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


class ArtifactRegistry:
    """Register, list, promote, and tag built artifacts."""

    def __init__(self, db: StateDatabase) -> None:
        self.db = db

    def register(
        self,
        artifact_name: str,
        fingerprint: str,
        *,
        build_id: int | None = None,
        version: str | None = None,
        stage: str = "dev",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> RegistryEntry:
        if stage not in STAGES:
            raise ValueError(f"Invalid stage '{stage}'. Use: {', '.join(STAGES)}")
        if not version:
            version = self._next_version(artifact_name)
        entry_id = self.db.register_artifact_version(
            artifact_name,
            version,
            fingerprint=fingerprint,
            build_id=build_id,
            stage=stage,
            tags=tags or [],
            metadata=metadata or {},
            metrics=metrics or {},
        )
        return self.get(artifact_name, version)  # type: ignore[return-value]

    def list(
        self,
        artifact_name: str | None = None,
        *,
        stage: str | None = None,
        tag: str | None = None,
        limit: int = 50,
    ) -> list[RegistryEntry]:
        rows = self.db.list_registry_versions(
            artifact_name=artifact_name,
            stage=stage,
            tag=tag,
            limit=limit,
        )
        return [self._row_to_entry(row) for row in rows]

    def get(self, artifact_name: str, version: str) -> RegistryEntry | None:
        row = self.db.get_registry_version(artifact_name, version)
        return self._row_to_entry(row) if row else None

    def get_latest(self, artifact_name: str, *, stage: str | None = None) -> RegistryEntry | None:
        row = self.db.get_latest_registry_version(artifact_name, stage=stage)
        return self._row_to_entry(row) if row else None

    def promote(self, artifact_name: str, version: str, stage: str) -> RegistryEntry:
        if stage not in STAGES:
            raise ValueError(f"Invalid stage '{stage}'. Use: {', '.join(STAGES)}")
        if not self.db.promote_registry_version(artifact_name, version, stage):
            raise ValueError(f"Registry entry not found: {artifact_name}@{version}")
        return self.get(artifact_name, version)  # type: ignore[return-value]

    def tag(self, artifact_name: str, version: str, tags: list[str]) -> RegistryEntry:
        if not self.db.tag_registry_version(artifact_name, version, tags):
            raise ValueError(f"Registry entry not found: {artifact_name}@{version}")
        return self.get(artifact_name, version)  # type: ignore[return-value]

    def _next_version(self, artifact_name: str) -> str:
        latest = self.get_latest(artifact_name)
        if latest is None:
            return "v1"
        try:
            num = int(latest.version.lstrip("v"))
            return f"v{num + 1}"
        except ValueError:
            return f"v{latest.id + 1}"

    @staticmethod
    def _row_to_entry(row: dict[str, Any]) -> RegistryEntry:
        created = row.get("created_at")
        return RegistryEntry(
            id=row["id"],
            artifact_name=row["artifact_name"],
            version=row["version"],
            fingerprint=row["fingerprint"],
            build_id=row.get("build_id"),
            stage=row.get("stage", "dev"),
            tags=row.get("tags") or [],
            metadata=row.get("metadata") or {},
            metrics=row.get("metrics") or {},
            created_at=datetime.fromisoformat(created) if created else None,
        )
