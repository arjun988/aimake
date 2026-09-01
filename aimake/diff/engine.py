"""Diff engine for comparing artifact versions."""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aimake.config.schema import ArtifactConfig
from aimake.hashing.files import hash_file


@dataclass
class DiffChange:
    """A single detected change."""

    field: str
    old_value: Any = None
    new_value: Any = None
    description: str = ""


@dataclass
class DiffResult:
    """Result of comparing an artifact between two states."""

    artifact: str
    artifact_type: str
    baseline: str
    has_changes: bool = False
    changes: list[DiffChange] = field(default_factory=list)
    unified_diff: str = ""
    summary: str = ""


class DiffEngine:
    """Compare artifacts across baselines (stored state, lock file, build)."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def diff_artifact(
        self,
        name: str,
        config: ArtifactConfig,
        *,
        current_fingerprint: str | None,
        baseline_fingerprint: str | None,
        baseline_label: str = "stored",
        baseline_snapshot: dict[str, Any] | None = None,
    ) -> DiffResult:
        if config.type == "prompt":
            return self._diff_prompt(
                name, config, current_fingerprint, baseline_fingerprint,
                baseline_label, baseline_snapshot,
            )
        if config.type == "dataset":
            return self._diff_dataset(
                name, config, current_fingerprint, baseline_fingerprint,
                baseline_label, baseline_snapshot,
            )
        if config.type == "model":
            return self._diff_model(
                name, config, current_fingerprint, baseline_fingerprint,
                baseline_label, baseline_snapshot,
            )
        return self._diff_generic(
            name, config, current_fingerprint, baseline_fingerprint, baseline_label
        )

    def _diff_prompt(
        self,
        name: str,
        config: ArtifactConfig,
        current_fp: str | None,
        baseline_fp: str | None,
        baseline_label: str,
        baseline_snapshot: dict[str, Any] | None,
    ) -> DiffResult:
        result = DiffResult(artifact=name, artifact_type="prompt", baseline=baseline_label)
        if not config.source:
            result.summary = "No prompt source configured."
            return result

        path = self.project_root / config.source
        if not path.is_file():
            result.summary = f"Prompt file not found: {config.source}"
            return result

        current_text = path.read_text(encoding="utf-8")
        old_text = (baseline_snapshot or {}).get("prompt_text", "")
        changes: list[DiffChange] = []

        if current_fp != baseline_fp:
            result.has_changes = True
            changes.append(DiffChange(
                field="fingerprint",
                old_value=baseline_fp,
                new_value=current_fp,
                description="Prompt fingerprint changed",
            ))

        if old_text and old_text != current_text:
            result.has_changes = True
            old_lines = old_text.count("\n") + 1
            new_lines = current_text.count("\n") + 1
            changes.append(DiffChange(
                field="content",
                old_value=f"{len(old_text)} chars, {old_lines} lines",
                new_value=f"{len(current_text)} chars, {new_lines} lines",
                description="Prompt text changed",
            ))
            result.unified_diff = self._text_diff(
                f"{name} ({baseline_label})",
                f"{name} (current)",
                old_text,
                current_text,
            )
        elif current_fp != baseline_fp and not old_text:
            result.has_changes = True
            changes.append(DiffChange(
                field="content",
                new_value=f"{len(current_text)} chars",
                description="Prompt changed (no stored snapshot — rebuild to capture diffs)",
            ))

        result.changes = changes
        result.summary = (
            f"Prompt '{config.source}' changed ({len(current_text)} chars)."
            if result.has_changes
            else f"Prompt '{config.source}' unchanged."
        )
        return result

    def _diff_dataset(
        self,
        name: str,
        config: ArtifactConfig,
        current_fp: str | None,
        baseline_fp: str | None,
        baseline_label: str,
        baseline_snapshot: dict[str, Any] | None,
    ) -> DiffResult:
        result = DiffResult(artifact=name, artifact_type="dataset", baseline=baseline_label)
        if not config.source:
            result.summary = "No dataset source configured."
            return result

        path = self.project_root / config.source
        if not path.exists():
            result.summary = f"Dataset not found: {config.source}"
            return result

        changes: list[DiffChange] = []
        if current_fp != baseline_fp:
            result.has_changes = True
            changes.append(DiffChange(
                field="fingerprint",
                old_value=baseline_fp,
                new_value=current_fp,
                description="Dataset fingerprint changed",
            ))

        current_stats = self._dataset_stats_dict(path)
        old_stats = baseline_snapshot or {}

        if old_stats:
            for key in ("row_count", "size_bytes", "file_hash", "file_count"):
                old_val = old_stats.get(key)
                new_val = current_stats.get(key)
                if old_val is not None and new_val is not None and old_val != new_val:
                    changes.append(DiffChange(
                        field=key,
                        old_value=old_val,
                        new_value=new_val,
                        description=f"Dataset {key} changed",
                    ))

            old_sample = old_stats.get("sample_rows", [])
            new_sample = current_stats.get("sample_rows", [])
            if old_sample != new_sample:
                changes.append(DiffChange(
                    field="sample_rows",
                    old_value=old_sample[:3],
                    new_value=new_sample[:3],
                    description="Sample rows changed",
                ))
                if old_sample and new_sample:
                    result.unified_diff = self._text_diff(
                        "sample (baseline)",
                        "sample (current)",
                        "\n".join(old_sample[:10]),
                        "\n".join(new_sample[:10]),
                    )

        changes.append(DiffChange(
            field="stats",
            old_value=self._format_stats(old_stats) if old_stats else None,
            new_value=self._format_stats(current_stats),
            description="Dataset statistics",
        ))

        result.changes = changes
        stats_str = self._format_stats(current_stats)
        result.summary = (
            f"Dataset changed: {stats_str}"
            if result.has_changes
            else f"Dataset unchanged: {stats_str}"
        )
        return result

    def _diff_model(
        self,
        name: str,
        config: ArtifactConfig,
        current_fp: str | None,
        baseline_fp: str | None,
        baseline_label: str,
        baseline_snapshot: dict[str, Any] | None,
    ) -> DiffResult:
        result = DiffResult(artifact=name, artifact_type="model", baseline=baseline_label)
        changes: list[DiffChange] = []
        old_snap = baseline_snapshot or {}

        if current_fp != baseline_fp:
            result.has_changes = True
            changes.append(DiffChange(
                field="fingerprint",
                old_value=baseline_fp,
                new_value=current_fp,
                description="Model fingerprint changed",
            ))

        old_params = old_snap.get("parameters", {})
        new_params = dict(config.parameters)
        if old_params != new_params:
            result.has_changes = True
            added = {k: v for k, v in new_params.items() if k not in old_params}
            removed = {k: v for k, v in old_params.items() if k not in new_params}
            changed = {
                k: (old_params[k], new_params[k])
                for k in new_params
                if k in old_params and old_params[k] != new_params[k]
            }
            changes.append(DiffChange(
                field="parameters",
                old_value=old_params or None,
                new_value=new_params or None,
                description="Model parameters changed",
            ))
            if added or removed or changed:
                diff_lines = []
                for k, v in sorted(added.items()):
                    diff_lines.append(f"+ {k}: {v}")
                for k, v in sorted(removed.items()):
                    diff_lines.append(f"- {k}: {v}")
                for k, (o, n) in sorted(changed.items()):
                    diff_lines.append(f"~ {k}: {o} -> {n}")
                result.unified_diff = "\n".join(diff_lines)

        if config.source:
            path = self.project_root / config.source
            if path.is_file():
                new_hash = hash_file(path)
                old_hash = old_snap.get("source_hash")
                if old_hash and old_hash != new_hash:
                    result.has_changes = True
                    changes.append(DiffChange(
                        field="source_hash",
                        old_value=old_hash,
                        new_value=new_hash,
                        description=f"Model source '{config.source}' changed",
                    ))

        result.changes = changes
        result.summary = (
            "Model configuration or source changed."
            if result.has_changes
            else "Model unchanged."
        )
        return result

    def _diff_generic(
        self,
        name: str,
        config: ArtifactConfig,
        current_fp: str | None,
        baseline_fp: str | None,
        baseline_label: str,
    ) -> DiffResult:
        result = DiffResult(artifact=name, artifact_type=config.type, baseline=baseline_label)
        if current_fp != baseline_fp:
            result.has_changes = True
            result.changes = [DiffChange(
                field="fingerprint",
                old_value=baseline_fp,
                new_value=current_fp,
                description="Artifact fingerprint changed",
            )]
            result.summary = f"{name} changed since {baseline_label}."
        else:
            result.summary = f"{name} unchanged since {baseline_label}."
        return result

    def _dataset_stats_dict(self, path: Path) -> dict[str, Any]:
        if path.is_file():
            stats: dict[str, Any] = {
                "size_bytes": path.stat().st_size,
                "file_hash": hash_file(path),
            }
            if path.suffix == ".jsonl":
                with open(path, encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
                stats["row_count"] = len(lines)
                stats["sample_rows"] = lines[:5]
            return stats
        if path.is_dir():
            files = sorted(p for p in path.rglob("*") if p.is_file())
            return {
                "file_count": len(files),
                "size_bytes": sum(f.stat().st_size for f in files),
            }
        return {}

    @staticmethod
    def _format_stats(stats: dict[str, Any]) -> str:
        if not stats:
            return "unknown"
        parts = []
        if "row_count" in stats:
            parts.append(f"{stats['row_count']} rows")
        if "size_bytes" in stats:
            parts.append(f"{stats['size_bytes']} bytes")
        if "file_count" in stats:
            parts.append(f"{stats['file_count']} files")
        return ", ".join(parts) if parts else str(stats)

    @staticmethod
    def _text_diff(label_a: str, label_b: str, text_a: str, text_b: str) -> str:
        diff = difflib.unified_diff(
            text_a.splitlines(keepends=True),
            text_b.splitlines(keepends=True),
            fromfile=label_a,
            tofile=label_b,
        )
        return "".join(diff)
