"""Unified cache interface combining SQLite metadata and filesystem storage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aimake.cache.filesystem import FilesystemCache
from aimake.models import ArtifactStatus
from aimake.state.database import StateDatabase


class Cache:
    """High-level cache coordinating state DB and filesystem cache."""

    def __init__(self, aimake_dir: Path, project_root: Path) -> None:
        self.aimake_dir = aimake_dir
        self.project_root = project_root
        self.db = StateDatabase(aimake_dir)
        self.fs = FilesystemCache(aimake_dir)

    def close(self) -> None:
        self.db.close()

    def get_stored_fingerprints(self) -> dict[str, str]:
        return self.db.get_fingerprints()

    def get_artifact_state(self, name: str):
        return self.db.get_artifact(name)

    def get_all_states(self) -> dict[str, Any]:
        return self.db.get_all_artifacts()

    def is_cache_hit(self, name: str, fingerprint: str) -> bool:
        """Check if artifact can be restored from cache."""
        stored = self.db.get_artifact(name)
        if stored and stored.fingerprint == fingerprint:
            if self.fs.has(fingerprint):
                return self.fs.verify(fingerprint)
        return self.fs.has(fingerprint) and self.fs.verify(fingerprint)

    def restore(self, name: str, fingerprint: str, outputs: list[str]) -> bool:
        """Restore artifact from cache."""
        if not self.fs.has(fingerprint):
            return False
        return self.fs.restore(fingerprint, outputs, self.project_root)

    def store(
        self,
        name: str,
        fingerprint: str,
        *,
        artifact_type: str = "generic",
        command: str | None = None,
        outputs: list[str] | None = None,
        duration: float | None = None,
        metadata: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        exit_code: int = 0,
    ) -> None:
        """Store artifact in cache after successful build."""
        outputs = outputs or []
        self.fs.store(
            fingerprint,
            name,
            outputs,
            self.project_root,
            command=command,
            duration=duration,
            metadata=metadata,
        )
        self.db.save_artifact(
            name,
            fingerprint=fingerprint,
            status=ArtifactStatus.SUCCESS,
            artifact_type=artifact_type,
            command=command,
            outputs=outputs,
            metadata=metadata,
            metrics=metrics,
            duration=duration,
            exit_code=exit_code,
        )

    def invalidate(self, name: str) -> None:
        """Remove artifact from state (not filesystem cache)."""
        state = self.db.get_artifact(name)
        if state and state.fingerprint:
            self.fs.remove(state.fingerprint)
        self.db.delete_artifact(name)

    def clear_all(self) -> None:
        """Clear all cache and state."""
        self.fs.clear()
        self.db.clear_artifacts()

    def verify_integrity(self) -> list[str]:
        """Check cache integrity, return list of corrupted entries."""
        corrupted = []
        for fp in self.fs.list_entries():
            if not self.fs.verify(fp):
                corrupted.append(fp)
        return corrupted

    @property
    def state_db(self) -> StateDatabase:
        return self.db
