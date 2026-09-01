"""Project lock file management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from aimake.constants import LOCK_FILE


def generate_lock(
    project_name: str,
    fingerprints: dict[str, str],
) -> dict[str, Any]:
    """Generate lock file content from current fingerprints."""
    return {
        "version": 1,
        "project": {"name": project_name},
        "artifacts": {
            name: {"fingerprint": fp}
            for name, fp in sorted(fingerprints.items())
        },
    }


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
