"""Reproducibility report generation."""

from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aimake.config.schema import AimakeConfig
from aimake.git.integration import get_git_info
from aimake.hashing.external_probe import probe_artifact_externals
from aimake.lock import lock_fingerprints, read_lock
from aimake.project import Project


def build_repro_report(project: Project) -> dict[str, Any]:
    """Collect env, deps, fingerprints, lock diffs, and drift probes."""
    config = project.config
    root = project.project_root
    git = get_git_info(root)
    fps = project.runner.compute_fingerprints()
    statuses = project.runner.compute_statuses()
    stored = project.cache.get_stored_fingerprints()
    lock = read_lock(root)
    lock_fps = lock_fingerprints(lock)

    artifacts = []
    for name in project.graph.names():
        node = project.graph.get(name)
        probes = []
        if node.config.external:
            for p in probe_artifact_externals(node.config.external):
                probes.append(
                    {
                        "name": p.name,
                        "provider": p.provider,
                        "pinned": p.pinned_revision,
                        "live": p.live_revision,
                        "drifted": p.drifted,
                        "ok": p.ok,
                        "detail": p.detail,
                    }
                )
        artifacts.append(
            {
                "name": name,
                "type": node.config.type,
                "fingerprint": fps.get(name),
                "stored_fingerprint": stored.get(name),
                "lock_fingerprint": lock_fps.get(name),
                "status": statuses.get(name).value if name in statuses else None,
                "depends_on": list(node.config.depends_on),
                "outputs": list(node.config.outputs),
                "external": [
                    {
                        "name": e.name,
                        "provider": e.provider,
                        "model": e.model,
                        "revision": e.revision,
                        "probe": e.probe,
                        "probe_mode": e.probe_mode,
                    }
                    for e in node.config.external
                ],
                "probes": probes,
                "fingerprint_matches_stored": fps.get(name) == stored.get(name),
                "fingerprint_matches_lock": (
                    fps.get(name) == lock_fps.get(name) if name in lock_fps else None
                ),
            }
        )

    attest_dir = root / ".aimake" / "attestations"
    attestations = []
    if attest_dir.is_dir():
        for art_dir in sorted(attest_dir.iterdir()):
            latest = art_dir / "latest.json"
            if latest.is_file():
                attestations.append(
                    {
                        "artifact": art_dir.name,
                        "path": str(latest.relative_to(root)),
                    }
                )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aimake_version": _version(),
        "project": {
            "name": config.project.name,
            "version": config.project.version,
            "root": str(root),
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "environment_mode": config.project.environment_mode,
            "tracked_vars": list(config.environment),
        },
        "git": {
            "available": git.available,
            "commit": git.commit,
            "branch": git.branch,
            "dirty": git.dirty,
        },
        "cache": {
            "remote_enabled": bool(config.cache.remote),
            "team_id": config.cache.remote.team_id if config.cache.remote else None,
        },
        "lock": {
            "present": lock is not None,
            "version": lock.get("version") if lock else None,
            "remote": (lock or {}).get("cache", {}).get("remote"),
        },
        "artifacts": artifacts,
        "attestations": attestations,
        "attestation_enabled": config.attestation.enabled,
        "lineage_enabled": config.lineage.enabled,
    }


def render_repro_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# aimake reproducibility report",
        "",
        f"Generated: `{report['generated_at']}`  ",
        f"aimake: `{report['aimake_version']}`  ",
        f"Project: **{report['project']['name']}** v{report['project']['version']}",
        "",
        "## Environment",
        "",
        f"- Python: `{report['environment']['python']}`",
        f"- Platform: `{report['environment']['platform']}`",
        f"- Env mode: `{report['environment']['environment_mode']}`",
        "",
        "## Git",
        "",
    ]
    git = report["git"]
    if git.get("available"):
        lines += [
            f"- Commit: `{git.get('commit')}`",
            f"- Branch: `{git.get('branch')}`",
            f"- Dirty: `{git.get('dirty')}`",
            "",
        ]
    else:
        lines += ["- Not a git repository", ""]

    lines += ["## Artifacts", "", "| Artifact | Status | FP match stored | FP match lock | Drift |", "|---|---|---|---|---|"]
    for a in report["artifacts"]:
        drift = "yes" if any(p.get("drifted") for p in a.get("probes") or []) else "—"
        lines.append(
            f"| `{a['name']}` | {a.get('status')} | "
            f"{a.get('fingerprint_matches_stored')} | "
            f"{a.get('fingerprint_matches_lock')} | {drift} |"
        )
    lines += ["", "## Fingerprints", ""]
    for a in report["artifacts"]:
        lines.append(f"### `{a['name']}`")
        lines.append(f"- current: `{a.get('fingerprint')}`")
        lines.append(f"- stored: `{a.get('stored_fingerprint')}`")
        lines.append(f"- lock: `{a.get('lock_fingerprint')}`")
        lines.append("")

    if report.get("attestations"):
        lines += ["## Attestations", ""]
        for att in report["attestations"]:
            lines.append(f"- `{att['artifact']}` → `{att['path']}`")
        lines.append("")

    return "\n".join(lines) + "\n"


def write_repro_report(
    project: Project,
    *,
    fmt: str = "markdown",
    output: Path | None = None,
) -> Path:
    report = build_repro_report(project)
    root = project.project_root
    out_dir = root / ".aimake" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if fmt == "json":
        path = output or (out_dir / f"repro-{stamp}.json")
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return path

    if fmt == "pdf":
        # Lightweight PDF via reportlab if available; else write HTML-ish markdown note
        md = render_repro_markdown(report)
        path = output or (out_dir / f"repro-{stamp}.pdf")
        try:
            _write_simple_pdf(path, md)
        except Exception:
            # Fallback: write .md and point user to markdown
            path = output or (out_dir / f"repro-{stamp}.md")
            path.write_text(md, encoding="utf-8")
        return path

    path = output or (out_dir / f"repro-{stamp}.md")
    path.write_text(render_repro_markdown(report), encoding="utf-8")
    return path


def _write_simple_pdf(path: Path, markdown_text: str) -> None:
    """Minimal PDF writer without hard dependency (plain text pages)."""
    # Very small PDF with Helvetica text lines
    lines = markdown_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").splitlines()
    content_lines = ["BT", "/F1 10 Tf", "50 750 Td", "12 TL"]
    for i, line in enumerate(lines[:60]):
        safe = line[:100]
        if i == 0:
            content_lines.append(f"({safe}) Tj")
        else:
            content_lines.append(f"T* ({safe}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")
    objs = []
    objs.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objs.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objs.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objs.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("latin-1")
        + stream
        + b"\nendstream\nendobj\n"
    )
    objs.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "latin-1"
        )
    )
    path.write_bytes(bytes(out))


def _version() -> str:
    try:
        from aimake import __version__

        return __version__
    except Exception:
        return "unknown"
