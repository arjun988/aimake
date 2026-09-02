"""Unified cache interface with optional remote (S3) backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aimake.cache.filesystem import FilesystemCache
from aimake.cache.s3 import S3Cache
from aimake.config.schema import AimakeConfig, RemoteCacheConfig
from aimake.models import ArtifactStatus
from aimake.state.database import StateDatabase


class Cache:
    """High-level cache coordinating state DB, local filesystem, and remote storage."""

    def __init__(
        self,
        aimake_dir: Path,
        project_root: Path,
        config: AimakeConfig | None = None,
    ) -> None:
        self.aimake_dir = aimake_dir
        self.project_root = project_root
        self.config = config
        self.db = StateDatabase(aimake_dir)
        self.fs = FilesystemCache(aimake_dir)
        self.remote: S3Cache | None = None
        self.remote_config: RemoteCacheConfig | None = None

        if config and config.cache.remote:
            self.remote_config = config.cache.remote
            if config.cache.remote.type == "s3" and config.cache.remote.s3:
                from copy import deepcopy

                from aimake.config.schema import S3CacheConfig

                s3_cfg = deepcopy(config.cache.remote.s3)
                team = config.cache.remote.team_id
                if team:
                    base = s3_cfg.prefix.rstrip("/")
                    s3_cfg = S3CacheConfig(
                        bucket=s3_cfg.bucket,
                        prefix=f"{base}/{team}/",
                        region=s3_cfg.region,
                        endpoint_url=s3_cfg.endpoint_url,
                    )
                self.remote = S3Cache(s3_cfg)

    def close(self) -> None:
        self.db.close()

    def get_stored_fingerprints(self) -> dict[str, str]:
        return self.db.get_fingerprints()

    def get_artifact_state(self, name: str):
        return self.db.get_artifact(name)

    def get_all_states(self) -> dict[str, Any]:
        return self.db.get_all_artifacts()

    def is_cache_hit(self, name: str, fingerprint: str) -> bool:
        """Check if artifact can be restored from local or remote cache."""
        if self.fs.has(fingerprint) and self.fs.verify(fingerprint):
            return True
        if self.remote and self.remote_config and self.remote_config.auto_pull:
            if self.remote.has(fingerprint):
                self.remote.pull(fingerprint, self.fs)
                return self.fs.has(fingerprint) and self.fs.verify(fingerprint)
        return False

    def restore(self, name: str, fingerprint: str, outputs: list[str]) -> bool:
        """Restore artifact from cache (local first, then remote)."""
        if not self.fs.has(fingerprint) and self.remote and self.remote_config:
            if self.remote_config.auto_pull and self.remote.has(fingerprint):
                self.remote.pull(fingerprint, self.fs)
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
        """Store artifact in local cache and optionally push to remote."""
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
        if self.remote and self.remote_config and self.remote_config.auto_push:
            self.remote.push(fingerprint, self.fs)

    def push_remote(self, fingerprint: str | None = None) -> list[str]:
        """Push cache entries to remote storage."""
        if not self.remote:
            return []
        pushed: list[str] = []
        fps = [fingerprint] if fingerprint else self.fs.list_entries()
        for fp in fps:
            full_fp = fp if fp.startswith("sha256:") else f"sha256:{fp}"
            if self.remote.push(full_fp, self.fs):
                pushed.append(full_fp)
        return pushed

    def pull_remote(self, fingerprint: str | None = None) -> list[str]:
        """Pull cache entries from remote storage."""
        if not self.remote:
            return []
        pulled: list[str] = []
        if fingerprint:
            fps = [fingerprint]
        else:
            fps = [f"sha256:{fp}" for fp in self.remote.list_entries()]
        for fp in fps:
            if self.remote.pull(fp, self.fs):
                pulled.append(fp)
        return pulled

    def remote_status(self) -> dict[str, Any]:
        """Return remote cache status."""
        local = set(self.fs.list_entries())
        team_id = self.remote_config.team_id if self.remote_config else None
        s3 = self.remote_config.s3 if self.remote_config else None
        identity = {
            "team_id": team_id,
            "bucket": s3.bucket if s3 else None,
            "prefix": (
                f"{s3.prefix.rstrip('/')}/{team_id}/" if s3 and team_id
                else (s3.prefix if s3 else None)
            ),
        }
        if not self.remote:
            return {
                "enabled": False,
                "local_entries": len(local),
                "team": identity,
            }
        remote = set(self.remote.list_entries())
        return {
            "enabled": True,
            "type": self.remote_config.type if self.remote_config else "unknown",
            "local_entries": len(local),
            "remote_entries": len(remote),
            "only_local": sorted(local - remote),
            "only_remote": sorted(remote - local),
            "synced": sorted(local & remote),
            "team": identity,
        }

    def pull_lock_fingerprints(self, fingerprints: dict[str, str]) -> list[str]:
        """Pull specific fingerprints referenced by aimake.lock (shared team cache)."""
        if not self.remote:
            return []
        pulled: list[str] = []
        for fp in fingerprints.values():
            full = fp if fp.startswith("sha256:") else f"sha256:{fp}"
            if self.remote.pull(full, self.fs):
                pulled.append(full)
        return pulled

    def invalidate(self, name: str) -> None:
        state = self.db.get_artifact(name)
        if state and state.fingerprint:
            self.fs.remove(state.fingerprint)
        self.db.delete_artifact(name)

    def clear_all(self) -> None:
        self.fs.clear()
        self.db.clear_artifacts()

    def clear_remote(self) -> None:
        if self.remote:
            self.remote.clear()

    def verify_integrity(self) -> list[str]:
        corrupted = []
        for fp in self.fs.list_entries():
            if not self.fs.verify(fp):
                corrupted.append(fp)
        return corrupted

    @property
    def state_db(self) -> StateDatabase:
        return self.db
