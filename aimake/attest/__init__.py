"""SLSA-style build provenance / output attestation."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aimake.config.schema import AimakeConfig, AttestationConfig
from aimake.git.integration import get_git_info


def build_attestation(
    *,
    project_root: Path,
    config: AimakeConfig,
    artifact: str,
    fingerprint: str,
    outputs: list[str],
    build_id: int | None = None,
    command: str | None = None,
    dependencies: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an unsigned in-toto / SLSA-lite provenance document."""
    git = get_git_info(project_root)
    cfg: AttestationConfig = config.attestation
    materials = []
    for dep in dependencies or []:
        materials.append({"uri": f"artifact://{dep}", "digest": {}})
    for rel in outputs:
        path = project_root / rel
        entry: dict[str, Any] = {"uri": rel}
        if path.is_file():
            h = hashlib.sha256(path.read_bytes()).hexdigest()
            entry["digest"] = {"sha256": h}
            entry["size"] = path.stat().st_size
        materials.append(entry)

    predicate: dict[str, Any] = {
        "buildType": "https://aimake.dev/attestation/v1",
        "builder": {
            "id": "aimake",
            "version": _aimake_version(),
            "platform": {
                "python": sys.version.split()[0],
                "system": platform.system(),
                "machine": platform.machine(),
            },
        },
        "invocation": {
            "configSource": {
                "uri": "aimake.yaml",
                "digest": _file_digest(project_root / "aimake.yaml"),
            },
            "parameters": {
                "artifact": artifact,
                "command": command,
                "build_id": build_id,
            },
        },
        "metadata": {
            "buildStartedOn": datetime.now(timezone.utc).isoformat(),
            "completeness": {"parameters": True, "environment": cfg.include_environment},
            "reproducible": not (git.dirty if git.available else True),
        },
        "materials": materials,
    }
    if git.available:
        predicate["metadata"]["git"] = {
            "commit": git.commit,
            "branch": git.branch,
            "dirty": git.dirty,
        }
    if cfg.include_environment:
        predicate["metadata"]["environment_vars"] = sorted(
            set(config.environment + (config.artifacts.get(artifact).environment if artifact in config.artifacts else []))
        )
    if metrics:
        predicate["metadata"]["metrics"] = metrics
    if extra:
        predicate["metadata"]["extra"] = extra

    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {
                "name": artifact,
                "digest": {"sha256": fingerprint.replace("sha256:", "")},
            }
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": predicate,
        "aimake": {
            "fingerprint": fingerprint,
            "project": config.project.name,
            "version": config.project.version,
        },
    }


def write_attestation(
    project_root: Path,
    config: AimakeConfig,
    document: dict[str, Any],
    artifact: str,
    fingerprint: str,
) -> Path | None:
    if not config.attestation.enabled or not config.attestation.write_sidecars:
        return None
    safe_fp = fingerprint.replace("sha256:", "")[:16]
    dest_dir = project_root / ".aimake" / "attestations" / artifact
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{safe_fp}.json"
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    latest = dest_dir / "latest.json"
    latest.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return path


def _aimake_version() -> str:
    try:
        from aimake import __version__

        return __version__
    except Exception:
        return "unknown"


def _file_digest(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
