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

    return manager
