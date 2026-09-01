"""Capture artifact snapshots for rich diffs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aimake.config.schema import ArtifactConfig
from aimake.hashing.files import hash_file


def capture_snapshot(name: str, config: ArtifactConfig, project_root: Path) -> dict[str, Any]:
    """Capture a point-in-time snapshot of an artifact's diff-relevant state."""
    snapshot: dict[str, Any] = {
        "name": name,
        "type": config.type,
    }

    if config.type == "prompt" and config.source:
        path = project_root / config.source
        if path.is_file():
            snapshot["prompt_text"] = path.read_text(encoding="utf-8")
            snapshot["source"] = config.source
            snapshot["char_count"] = len(snapshot["prompt_text"])
            snapshot["line_count"] = snapshot["prompt_text"].count("\n") + 1

    elif config.type == "dataset" and config.source:
        path = project_root / config.source
        snapshot["source"] = config.source
        if path.is_file():
            snapshot["size_bytes"] = path.stat().st_size
            snapshot["file_hash"] = hash_file(path)
            if path.suffix == ".jsonl":
                with open(path, encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
                snapshot["row_count"] = len(lines)
                snapshot["sample_rows"] = lines[:5]
        elif path.is_dir():
            files = sorted(p for p in path.rglob("*") if p.is_file())
            snapshot["file_count"] = len(files)
            snapshot["size_bytes"] = sum(f.stat().st_size for f in files)

    elif config.type == "model":
        snapshot["parameters"] = dict(config.parameters)
        if config.source:
            path = project_root / config.source
            snapshot["source"] = config.source
            if path.is_file():
                snapshot["source_hash"] = hash_file(path)
                if path.suffix == ".json":
                    try:
                        snapshot["model_config"] = json.loads(
                            path.read_text(encoding="utf-8")
                        )
                    except json.JSONDecodeError:
                        pass

    elif config.source:
        path = project_root / config.source
        snapshot["source"] = config.source
        if path.is_file():
            snapshot["source_hash"] = hash_file(path)

    if config.command:
        snapshot["command"] = config.command
    if config.parameters:
        snapshot.setdefault("parameters", dict(config.parameters))

    return snapshot


def extract_snapshot(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """Extract stored snapshot from artifact metadata."""
    if not metadata:
        return None
    from aimake.hashing.file_cache import SNAPSHOT_KEY

    snap = metadata.get(SNAPSHOT_KEY)
    return snap if isinstance(snap, dict) else None


def merge_metadata_with_snapshot(
    user_metadata: dict[str, Any] | None,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Merge user metadata with internal snapshot."""
    from aimake.hashing.file_cache import SNAPSHOT_KEY

    merged = dict(user_metadata or {})
    merged[SNAPSHOT_KEY] = snapshot
    return merged
