"""Plugin interface for future integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AimakePlugin(ABC):
    """Base class for aimake plugins."""

    name: str = "base"
    version: str = "0.0.0"

    @abstractmethod
    def on_build_start(self, context: dict[str, Any]) -> None:
        """Called when a build starts."""

    @abstractmethod
    def on_build_finish(self, context: dict[str, Any]) -> None:
        """Called when a build finishes."""

    @abstractmethod
    def on_artifact_complete(self, context: dict[str, Any]) -> None:
        """Called when an artifact build completes."""


class PluginManager:
    """Manage loaded plugins."""

    def __init__(self) -> None:
        self._plugins: list[AimakePlugin] = []

    def register(self, plugin: AimakePlugin) -> None:
        self._plugins.append(plugin)

    @property
    def plugins(self) -> list[AimakePlugin]:
        return list(self._plugins)

    def emit(self, event: str, context: dict[str, Any]) -> None:
        for plugin in self._plugins:
            method = getattr(plugin, event, None)
            if method and callable(method):
                method(context)
