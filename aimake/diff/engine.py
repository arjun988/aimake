"""Diff engine for comparing artifact versions."""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aimake.config.schema import ArtifactConfig
from aimake.hashing.files import hash_file, hash_string


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
    ) -> DiffResult:
        if config.type == "prompt":
            return self._diff_prompt(name, config, current_fingerprint, baseline_fingerprint, baseline_label)
        if config.type == "dataset":
            return self._diff_dataset(name, config, current_fingerprint, baseline_fingerprint, baseline_label)
        if config.type == "model":
            return self._diff_model(name, config, current_fingerprint, baseline_fingerprint, baseline_label)
        return self._diff_generic(name, config, current_fingerprint, baseline_fingerprint, baseline_label)

    def _diff_prompt(
        self,
        name: str,
        config: ArtifactConfig,
        current_fp: str | None,
        baseline_fp: str | None,
        baseline_label: str,
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
        changes: list[DiffChange] = []

        if current_fp != baseline_fp:
            result.has_changes = True
            changes.append(DiffChange(
                field="fingerprint",
                old_value=baseline_fp,
                new_value=current_fp,
                description="Prompt fingerprint changed",
            ))

        if baseline_fp and current_fp and baseline_fp != current_fp:
            old_text = current_text  # without snapshot store, show content stats
            changes.append(DiffChange(
                field="content",
                old_value=f"{len(old_text)} chars",
                new_value=f"{len(current_text)} chars, {current_text.count(chr(10))+1} lines",
                description="Prompt content changed",
            ))
            result.unified_diff = self._text_diff(
                f"{name} ({baseline_label})",
                f"{name} (current)",
                "",  # no historical text without snapshot
                current_text,
            )

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

        stats = self._dataset_stats(path)
        changes.append(DiffChange(
            field="stats",
            new_value=stats,
            description="Current dataset statistics",
        ))

        if path.is_file() and path.suffix == ".jsonl":
            sample = self._jsonl_sample(path, 3)
            changes.append(DiffChange(
                field="sample",
                new_value=sample,
                description="Sample rows (first 3)",
            ))

        result.changes = changes
        result.summary = (
            f"Dataset changed: {stats}"
            if result.has_changes
            else f"Dataset unchanged: {stats}"
        )
        return result

    def _diff_model(
        self,
        name: str,
        config: ArtifactConfig,
        current_fp: str | None,
        baseline_fp: str | None,
        baseline_label: str,
    ) -> DiffResult:
        result = DiffResult(artifact=name, artifact_type="model", baseline=baseline_label)
        changes: list[DiffChange] = []

        if current_fp != baseline_fp:
            result.has_changes = True
            changes.append(DiffChange(
                field="fingerprint",
                old_value=baseline_fp,
                new_value=current_fp,
                description="Model fingerprint changed",
            ))

        if config.parameters:
            changes.append(DiffChange(
                field="parameters",
                new_value=config.parameters,
                description="Model parameters",
            ))

        if config.source:
            path = self.project_root / config.source
            if path.is_file():
                if path.suffix == ".json":
                    try:
                        model_cfg = json.loads(path.read_text(encoding="utf-8"))
                        changes.append(DiffChange(
                            field="model_config",
                            new_value=model_cfg,
                            description=f"Model config from {config.source}",
                        ))
                    except json.JSONDecodeError:
                        pass
                changes.append(DiffChange(
                    field="source_hash",
                    new_value=hash_file(path),
                    description=f"Hash of {config.source}",
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

    @staticmethod
    def _dataset_stats(path: Path) -> str:
        if path.is_file():
            size = path.stat().st_size
            rows = 0
            if path.suffix == ".jsonl":
                with open(path, encoding="utf-8") as f:
                    rows = sum(1 for line in f if line.strip())
            return f"{path.name}: {size} bytes, {rows} rows"
        if path.is_dir():
            files = list(path.rglob("*"))
            total = sum(f.stat().st_size for f in files if f.is_file())
            return f"{path.name}/: {len(files)} files, {total} bytes"
        return "unknown"

    @staticmethod
    def _jsonl_sample(path: Path, n: int = 3) -> list[str]:
        samples = []
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                if line.strip():
                    samples.append(line.strip()[:120])
        return samples

    @staticmethod
    def _text_diff(label_a: str, label_b: str, text_a: str, text_b: str) -> str:
        diff = difflib.unified_diff(
            text_a.splitlines(keepends=True),
            text_b.splitlines(keepends=True),
            fromfile=label_a,
            tofile=label_b,
        )
        return "".join(diff)

    def diff_prompt_text(self, config: ArtifactConfig, old_text: str) -> str:
        """Generate unified diff for prompt text."""
        if not config.source:
            return ""
        path = self.project_root / config.source
        if not path.is_file():
            return ""
        current = path.read_text(encoding="utf-8")
        return self._text_diff("previous", "current", old_text, current)
