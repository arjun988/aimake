"""Hugging Face Hub integration plugin."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from aimake.config.schema import HuggingFacePluginConfig
from aimake.plugins.base import AimakePlugin


def require_huggingface_hub():
    try:
        import huggingface_hub
    except ImportError as e:
        raise ImportError(
            "Hugging Face plugin requires huggingface_hub. "
            "Install with: pip install aimake[huggingface]"
        ) from e
    return huggingface_hub


class HuggingFacePlugin(AimakePlugin):
    """Pull and push models/datasets via the Hugging Face Hub."""

    name = "huggingface"
    version = "0.1.0"

    def __init__(self, config: HuggingFacePluginConfig, project_root: Path) -> None:
        self.config = config
        self.project_root = project_root
        self.cache_dir = (
            project_root / config.cache_dir
            if config.cache_dir
            else project_root / ".aimake" / "hf-cache"
        )

    def on_pre_artifact(self, context: dict[str, Any]) -> None:
        artifact_config = context.get("artifact_config")
        if artifact_config is None:
            return
        if self.should_pull(artifact_config, rebuilding=context.get("rebuilding", False)):
            self.pull(artifact_config, artifact_name=context.get("artifact", ""))

    def on_artifact_complete(self, context: dict[str, Any]) -> None:
        artifact_config = context.get("artifact_config")
        if artifact_config is None or not context.get("success", True):
            return
        if self.should_push(artifact_config):
            self.push(
                artifact_config,
                artifact_name=context.get("artifact", ""),
                metadata=context.get("metadata") or {},
            )

    @staticmethod
    def hf_metadata(artifact_config) -> dict[str, Any] | None:
        meta = artifact_config.metadata.get("huggingface")
        return meta if isinstance(meta, dict) and meta.get("repo_id") else None

    def should_pull(self, artifact_config, *, rebuilding: bool = False) -> bool:
        hf = self.hf_metadata(artifact_config)
        if not hf:
            return False
        if hf.get("pull") is False:
            return False
        source = artifact_config.source
        if source and not (self.project_root / source).exists():
            return True
        if not self.config.auto_pull and hf.get("pull") is not True:
            return False
        if hf.get("pull") == "always" and rebuilding:
            return True
        return rebuilding and hf.get("pull", True) is not False

    def should_push(self, artifact_config) -> bool:
        hf = self.hf_metadata(artifact_config)
        if not hf:
            return False
        if hf.get("push") is True:
            return True
        return self.config.auto_push and hf.get("push") is not False

    def pull(self, artifact_config, *, artifact_name: str = "") -> Path:
        """Download a Hub repo into the artifact source directory."""
        hf = self.hf_metadata(artifact_config)
        if not hf:
            raise ValueError(f"Artifact '{artifact_name}' has no huggingface metadata")

        require_huggingface_hub()
        from huggingface_hub import snapshot_download

        repo_id = hf["repo_id"]
        revision = hf.get("revision", "main")
        repo_type = hf.get("repo_type", "model")
        local_dir = self._local_path(artifact_config)
        local_dir.mkdir(parents=True, exist_ok=True)

        snapshot_download(
            repo_id=repo_id,
            repo_type=repo_type,
            revision=revision,
            local_dir=str(local_dir),
            cache_dir=str(self.cache_dir),
            token=self._token(),
        )
        return local_dir

    def push(
        self,
        artifact_config,
        *,
        artifact_name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Upload artifact outputs or source to the Hugging Face Hub."""
        hf = self.hf_metadata(artifact_config)
        if not hf:
            raise ValueError(f"Artifact '{artifact_name}' has no huggingface metadata")

        require_huggingface_hub()
        from huggingface_hub import HfApi

        repo_id = hf.get("push_repo_id") or hf["repo_id"]
        repo_type = hf.get("repo_type", "model")
        folder = self._push_path(artifact_config)
        if not folder.is_dir():
            raise FileNotFoundError(f"Nothing to push for '{artifact_name}': {folder}")

        api = HfApi(token=self._token())
        api.create_repo(repo_id=repo_id, repo_type=repo_type, exist_ok=True)
        api.upload_folder(
            folder_path=str(folder),
            repo_id=repo_id,
            repo_type=repo_type,
            commit_message=hf.get("commit_message", f"aimake push {artifact_name}"),
        )
        return repo_id

    def status(self, artifact_config) -> dict[str, Any]:
        """Return Hub linkage status for an artifact."""
        hf = self.hf_metadata(artifact_config)
        if not hf:
            return {"linked": False}
        local = self._local_path(artifact_config)
        return {
            "linked": True,
            "repo_id": hf["repo_id"],
            "revision": hf.get("revision", "main"),
            "repo_type": hf.get("repo_type", "model"),
            "local_path": str(local),
            "local_exists": local.exists(),
            "auto_pull": self.config.auto_pull,
            "auto_push": self.config.auto_push,
            "push_repo_id": hf.get("push_repo_id"),
        }

    def _token(self) -> str | None:
        return os.environ.get(self.config.token_env) or None

    def _local_path(self, artifact_config) -> Path:
        if not artifact_config.source:
            raise ValueError("Hugging Face artifacts require a 'source' path")
        return self.project_root / artifact_config.source

    def _push_path(self, artifact_config) -> Path:
        if artifact_config.outputs:
            path = self.project_root / artifact_config.outputs[0]
            return path if path.is_dir() else path.parent
        return self._local_path(artifact_config)
