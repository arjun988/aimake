"""Resolve artifact output paths (supports atomic staging during builds)."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_output(relative_path: str, *, mkdir: bool = True) -> Path:
    """Return the path where an artifact output should be written.

    During builds with atomic staging enabled, writes go under
    ``AIMAKE_STAGING_DIR`` and are promoted to the final path on success.
    """
    staging = os.environ.get("AIMAKE_STAGING_DIR")
    root = Path(staging) if staging else Path.cwd()
    path = root / relative_path
    if mkdir:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path
