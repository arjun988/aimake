"""Plugins package."""

from aimake.plugins.base import AimakePlugin, PluginManager
from aimake.plugins.huggingface import HuggingFacePlugin
from aimake.plugins.loader import load_plugins

__all__ = ["AimakePlugin", "HuggingFacePlugin", "PluginManager", "load_plugins"]
