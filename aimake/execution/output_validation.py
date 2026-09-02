"""Validate artifact outputs beyond mere existence checks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from aimake.config.schema import OutputValidationConfig


@dataclass
class ValidationResult:
    """Outcome of output validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)


class OutputValidator:
    """Check outputs for size, structure, and semantic invariants."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def validate(
        self,
        outputs: list[str],
        config: OutputValidationConfig | None,
        *,
        metrics_file: str | None = None,
    ) -> ValidationResult:
        if config is None:
            return ValidationResult(valid=True)

        errors: list[str] = []
        paths = list(outputs)
        if metrics_file and metrics_file not in paths:
            paths.append(metrics_file)

        if not paths and config.non_empty:
            errors.append("validation.non_empty set but artifact has no outputs")

        for rel in paths:
            path = self.project_root / rel
            errors.extend(self._validate_path(rel, path, config))

        return ValidationResult(valid=not errors, errors=errors)

    def _validate_path(
        self,
        rel: str,
        path: Path,
        config: OutputValidationConfig,
    ) -> list[str]:
        errors: list[str] = []

        if not path.exists():
            errors.append(f"{rel}: output missing")
            return errors

        if path.is_dir():
            if config.non_empty and not any(path.iterdir()):
                errors.append(f"{rel}: directory is empty")
            return errors

        size = path.stat().st_size
        if config.min_size_bytes is not None and size < config.min_size_bytes:
            errors.append(f"{rel}: size {size}B < min {config.min_size_bytes}B")
        if config.non_empty and size == 0:
            errors.append(f"{rel}: file is empty")

        if path.suffix == ".jsonl" and config.min_rows is not None:
            try:
                rows = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
            except OSError as e:
                errors.append(f"{rel}: cannot read jsonl ({e})")
                return errors
            if rows < config.min_rows:
                errors.append(f"{rel}: {rows} rows < min {config.min_rows}")

        if path.suffix == ".json" and (config.required_keys or config.min_value):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                errors.append(f"{rel}: invalid JSON ({e})")
                return errors
            if not isinstance(data, dict):
                errors.append(f"{rel}: expected JSON object")
                return errors
            for key in config.required_keys:
                if key not in data:
                    errors.append(f"{rel}: missing required key '{key}'")
            for key, minimum in (config.min_value or {}).items():
                if key not in data:
                    errors.append(f"{rel}: missing metric '{key}' for min_value check")
                else:
                    try:
                        if float(data[key]) < minimum:
                            errors.append(
                                f"{rel}: {key}={data[key]} below minimum {minimum}"
                            )
                    except (TypeError, ValueError):
                        errors.append(f"{rel}: metric '{key}' is not numeric")

        return errors
