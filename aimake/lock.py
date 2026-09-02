"""Project lock file management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from aimake.constants import LOCK_FILE


def remote_identity(cache_remote: Any | None) -> dict[str, Any] | None:
    """Serialize remote cache identity for the lockfile (team shared cache)."""
    if cache_remote is None:
        return None
    s3 = getattr(cache_remote, "s3", None)
    if not s3:
        return {"type": getattr(cache_remote, "type", "s3")}
    prefix = s3.prefix.rstrip("/") + "/"
    team = getattr(cache_remote, "team_id", None)
    if team:
        prefix = f"{prefix.rstrip('/')}/{team}/"
    return {
        "type": cache_remote.type,
        "team_id": team,
        "bucket": s3.bucket,
        "prefix": prefix,
        "region": s3.region,
        "endpoint_url": s3.endpoint_url,
    }


def generate_lock(
    project_name: str,
    fingerprints: dict[str, str],
    *,
    remote: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate lock file content from current fingerprints."""
    data: dict[str, Any] = {
        "version": 2,
        "project": {"name": project_name},
        "artifacts": {
            name: {"fingerprint": fp}
            for name, fp in sorted(fingerprints.items())
        },
    }
    if remote:
        data["cache"] = {"remote": remote}
    return data


def write_lock(project_root: Path, lock_data: dict[str, Any]) -> Path:
    """Write aimake.lock to project root."""
    lock_path = project_root / LOCK_FILE
    with open(lock_path, "w", encoding="utf-8") as f:
        yaml.dump(lock_data, f, default_flow_style=False, sort_keys=False)
    return lock_path


def read_lock(project_root: Path) -> dict[str, Any] | None:
    """Read existing lock file."""
    lock_path = project_root / LOCK_FILE
    if not lock_path.is_file():
        return None
    with open(lock_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def lock_fingerprints(lock: dict[str, Any] | None) -> dict[str, str]:
    if not lock or "artifacts" not in lock:
        return {}
    out: dict[str, str] = {}
    for name, entry in (lock.get("artifacts") or {}).items():
        if isinstance(entry, dict) and entry.get("fingerprint"):
            out[name] = entry["fingerprint"]
        elif isinstance(entry, str):
            out[name] = entry
    return out
