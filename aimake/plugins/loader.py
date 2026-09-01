"""Load plugins from project configuration."""

from __future__ import annotations

from pathlib import Path

from aimake.config.schema import AimakeConfig
from aimake.plugins.base import PluginManager


def load_plugins(config: AimakeConfig, project_root: Path) -> PluginManager:
    """Instantiate enabled plugins from aimake.yaml."""
    manager = PluginManager()

    hf_cfg = config.plugins.huggingface
    if hf_cfg and hf_cfg.enabled:
        from aimake.plugins.huggingface import HuggingFacePlugin

        manager.register(HuggingFacePlugin(hf_cfg, project_root))

    wandb_cfg = config.plugins.wandb
    if wandb_cfg and wandb_cfg.enabled:
        from aimake.plugins.wandb_plugin import WandbPlugin

        manager.register(WandbPlugin(wandb_cfg, project_root))

    dvc_cfg = config.plugins.dvc
    if dvc_cfg and dvc_cfg.enabled:
        from aimake.plugins.dvc import DvcPlugin

        manager.register(DvcPlugin(dvc_cfg, project_root))

    docker_cfg = config.plugins.docker
    if docker_cfg and docker_cfg.enabled:
        from aimake.plugins.docker_plugin import DockerPlugin

        manager.register(DockerPlugin(docker_cfg, project_root))

    ollama_cfg = config.plugins.ollama
    if ollama_cfg and ollama_cfg.enabled:
        from aimake.plugins.ollama import OllamaPlugin

        manager.register(OllamaPlugin(ollama_cfg, project_root))

    return manager
