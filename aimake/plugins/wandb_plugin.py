"""Weights & Biases experiment tracking plugin."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from aimake.config.schema import WandbPluginConfig
from aimake.plugins.base import AimakePlugin


def require_wandb():
    try:
        import wandb
    except ImportError as e:
        raise ImportError(
            "Weights & Biases plugin requires wandb. "
            "Install with: pip install aimake[wandb]"
        ) from e
    return wandb


class WandbPlugin(AimakePlugin):
    """Log metrics and artifacts to Weights & Biases."""

    name = "wandb"
    version = "1.1.0"

    def __init__(self, config: WandbPluginConfig, project_root: Path) -> None:
        self.config = config
        self.project_root = project_root

    def on_artifact_complete(self, context: dict[str, Any]) -> None:
        artifact_config = context.get("artifact_config")
        if artifact_config is None or not context.get("success", True):
            return
        if not self.should_log(artifact_config):
            return
        self.log(context)

    def on_build_finish(self, context: dict[str, Any]) -> None:
        result = context.get("result")
        if result is None or not getattr(result, "success", False):
            return
        if not self.config.project:
            return
        wandb = require_wandb()
        run = wandb.init(
            project=self.config.project,
            entity=self.config.entity,
            job_type="aimake-build",
            reinit=True,
            settings=wandb.Settings(silent=True),
        )
        try:
            run.summary["build_id"] = context.get("build_id")
            run.summary["artifacts_built"] = len(getattr(result, "built", []) or [])
            run.summary["artifacts_cached"] = len(getattr(result, "cached", []) or [])
            if getattr(result, "metrics", None):
                run.log(result.metrics)
        finally:
            run.finish()

    @staticmethod
    def wandb_metadata(artifact_config) -> dict[str, Any] | None:
        meta = artifact_config.metadata.get("wandb")
        return meta if isinstance(meta, dict) else None

    def should_log(self, artifact_config) -> bool:
        meta = self.wandb_metadata(artifact_config)
        if meta is None and not self.config.auto_log_metrics:
            return False
        if meta and meta.get("log") is False:
            return False
        return bool(
            meta
            or self.config.auto_log_metrics
            or self.config.auto_log_artifacts
        )

    def _run_config(self, artifact_config, context: dict[str, Any]) -> dict[str, Any]:
        meta = self.wandb_metadata(artifact_config) or {}
        return {
            "project": meta.get("project") or self.config.project,
            "entity": meta.get("entity") or self.config.entity,
            "name": meta.get("run_name") or context.get("artifact"),
            "job_type": meta.get("job_type", "aimake-artifact"),
            "tags": meta.get("tags", []),
        }

    def log(self, context: dict[str, Any]) -> None:
        """Log metrics and optional artifacts for one build step."""
        artifact_config = context["artifact_config"]
        meta = self.wandb_metadata(artifact_config) or {}
        run_cfg = self._run_config(artifact_config, context)

        if not run_cfg["project"]:
            raise ValueError(
                "wandb project is required. Set plugins.wandb.project or "
                "metadata.wandb.project on the artifact."
            )

        wandb = require_wandb()
        self._ensure_api_key()

        run = wandb.init(
            project=run_cfg["project"],
            entity=run_cfg["entity"],
            name=run_cfg["name"],
            job_type=run_cfg["job_type"],
            tags=run_cfg["tags"] or None,
            reinit=True,
            settings=wandb.Settings(silent=True),
        )
        try:
            metrics = context.get("metrics") or {}
            if metrics and self._log_metrics(artifact_config, meta):
                run.log(metrics)

            run.summary["fingerprint"] = context.get("fingerprint")
            run.summary["duration"] = context.get("duration")
            if context.get("build_id") is not None:
                run.summary["build_id"] = context["build_id"]

            if self._log_artifacts(artifact_config, meta):
                for output in context.get("outputs") or []:
                    path = self.project_root / output
                    if path.exists():
                        self._log_path(run, path, meta, context.get("artifact", ""))
        finally:
            run.finish()

    def sync(self, artifact_config, *, artifact_name: str = "", context: dict | None = None) -> None:
        """Manually log an artifact to W&B."""
        ctx = context or {
            "artifact_config": artifact_config,
            "artifact": artifact_name,
            "success": True,
            "metrics": {},
            "outputs": list(artifact_config.outputs),
            "fingerprint": "",
            "duration": None,
            "build_id": None,
        }
        self.log(ctx)

    def status(self, artifact_config) -> dict[str, Any]:
        meta = self.wandb_metadata(artifact_config)
        return {
            "linked": meta is not None or self.config.auto_log_metrics,
            "project": (meta or {}).get("project") or self.config.project,
            "entity": (meta or {}).get("entity") or self.config.entity,
            "log_metrics": self._log_metrics(artifact_config, meta or {}),
            "log_artifacts": self._log_artifacts(artifact_config, meta or {}),
        }

    def _log_metrics(self, artifact_config, meta: dict[str, Any]) -> bool:
        if meta.get("log_metrics") is False:
            return False
        if meta.get("log_metrics") is True:
            return True
        return self.config.auto_log_metrics

    def _log_artifacts(self, artifact_config, meta: dict[str, Any]) -> bool:
        if meta.get("log_artifacts") is True:
            return True
        if meta.get("log_artifacts") is False:
            return False
        return self.config.auto_log_artifacts

    def _log_path(self, run, path: Path, meta: dict[str, Any], artifact_name: str) -> None:
        wandb = require_wandb()
        artifact_type = meta.get("artifact_type", "dataset")
        name = meta.get("artifact_name") or artifact_name or path.name
        artifact = wandb.Artifact(name=name, type=artifact_type)
        if path.is_dir():
            artifact.add_dir(str(path))
        else:
            artifact.add_file(str(path))
        run.log_artifact(artifact)

    def _ensure_api_key(self) -> None:
        if os.environ.get(self.config.api_key_env):
            return
        wandb = require_wandb()
        if wandb.api.api_key:
            return
        raise ValueError(
            f"W&B API key not found. Set {self.config.api_key_env} or run wandb login."
        )
