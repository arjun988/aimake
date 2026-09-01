"""Ollama local LLM plugin."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from aimake.config.schema import OllamaPluginConfig
from aimake.plugins._cli import require_cli, run_cli
from aimake.plugins.base import AimakePlugin


class OllamaPlugin(AimakePlugin):
    """Pull and manage Ollama models for pipeline artifacts."""

    name = "ollama"
    version = "1.1.0"

    def __init__(self, config: OllamaPluginConfig, project_root: Path) -> None:
        self.config = config
        self.project_root = project_root

    def on_pre_artifact(self, context: dict[str, Any]) -> None:
        artifact_config = context.get("artifact_config")
        if artifact_config is None:
            return
        if self.should_pull(artifact_config, rebuilding=context.get("rebuilding", False)):
            self.pull(artifact_config, artifact_name=context.get("artifact", ""))

    @staticmethod
    def ollama_metadata(artifact_config) -> dict[str, Any] | None:
        meta = artifact_config.metadata.get("ollama")
        if isinstance(meta, dict) and meta.get("model"):
            return meta
        return None

    def model_name(self, artifact_config) -> str | None:
        meta = self.ollama_metadata(artifact_config)
        if not meta:
            return None
        model = meta["model"]
        tag = meta.get("tag")
        if tag and ":" not in model:
            return f"{model}:{tag}"
        return model

    def should_pull(self, artifact_config, *, rebuilding: bool = False) -> bool:
        meta = self.ollama_metadata(artifact_config)
        if not meta:
            return False
        if meta.get("pull") is False:
            return False
        model = self.model_name(artifact_config)
        if not model:
            return False
        if not self.config.auto_pull and meta.get("pull") is not True:
            return False
        if meta.get("pull") == "always" and rebuilding:
            return True
        if rebuilding and meta.get("pull", True) is not False:
            return not self.model_exists(model)
        return not self.model_exists(model)

    def pull(self, artifact_config, *, artifact_name: str = "") -> str:
        model = self.model_name(artifact_config)
        if not model:
            raise ValueError(f"Artifact '{artifact_name}' has no ollama.model configured")

        env = os.environ.copy()
        if self.config.host:
            env["OLLAMA_HOST"] = self.config.host

        try:
            require_cli("ollama", extra="ollama")
            run_cli(["ollama", "pull", model], cwd=self.project_root, env=env)
        except ImportError:
            self._pull_via_api(model)
        return model

    def model_exists(self, model: str) -> bool:
        models = self.list_models()
        base = model.split(":")[0]
        for name in models:
            if name == model or name == base or name.startswith(f"{base}:"):
                return True
        return False

    def list_models(self) -> list[str]:
        try:
            data = self._api_get("/api/tags")
            models = data.get("models", [])
            return [m.get("name", "") for m in models if m.get("name")]
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            try:
                require_cli("ollama", extra="ollama")
                result = run_cli(["ollama", "list"], cwd=self.project_root, check=False)
                if result.returncode != 0:
                    return []
                lines = [ln.split()[0] for ln in result.stdout.splitlines()[1:] if ln.strip()]
                return lines
            except ImportError:
                return []

    def status(self, artifact_config) -> dict[str, Any]:
        meta = self.ollama_metadata(artifact_config)
        if not meta:
            return {"linked": False}
        model = self.model_name(artifact_config)
        return {
            "linked": True,
            "model": model,
            "host": self.config.host,
            "local_exists": self.model_exists(model) if model else False,
            "auto_pull": self.config.auto_pull,
        }

    def _pull_via_api(self, model: str) -> None:
        payload = json.dumps({"name": model, "stream": False}).encode()
        req = urllib.request.Request(
            f"{self.config.host.rstrip('/')}/api/pull",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                resp.read()
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Failed to pull Ollama model '{model}' from {self.config.host}: {e}"
            ) from e

    def _api_get(self, path: str) -> dict[str, Any]:
        url = f"{self.config.host.rstrip('/')}{path}"
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode())
