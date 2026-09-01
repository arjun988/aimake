"""Plugins package."""

from aimake.plugins.base import AimakePlugin, PluginManager
from aimake.plugins.dvc import DvcPlugin
from aimake.plugins.docker_plugin import DockerPlugin
from aimake.plugins.huggingface import HuggingFacePlugin
from aimake.plugins.loader import load_plugins
from aimake.plugins.ollama import OllamaPlugin
from aimake.plugins.wandb_plugin import WandbPlugin

__all__ = [
    "AimakePlugin",
    "DvcPlugin",
    "DockerPlugin",
    "HuggingFacePlugin",
    "OllamaPlugin",
    "PluginManager",
    "WandbPlugin",
    "load_plugins",
]
