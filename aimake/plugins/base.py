"""Plugin interface for aimake integrations."""

from __future__ import annotations

from abc import ABC
from typing import Any


class AimakePlugin(ABC):
    """Base class for aimake plugins.

    Subclasses override only the hooks they need.
    """

    name: str = "base"
    version: str = "0.0.0"

    def on_build_start(self, context: dict[str, Any]) -> None:
        """Called when a build starts."""

    def on_build_finish(self, context: dict[str, Any]) -> None:
        """Called when a build finishes."""

    def on_pre_artifact(self, context: dict[str, Any]) -> None:
        """Called before an artifact is built (pull remote sources, etc.)."""

    def on_artifact_complete(self, context: dict[str, Any]) -> None:
        """Called when an artifact build completes (push, log, etc.)."""


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

    def get(self, name: str) -> AimakePlugin | None:
        for plugin in self._plugins:
            if plugin.name == name:
                return plugin
        return None

    def wrap_command(self, artifact: str, artifact_config: Any, command: str) -> str:
        """Let plugins rewrite commands (e.g. Docker run wrapper)."""
        for plugin in self._plugins:
            hook = getattr(plugin, "wrap_command", None)
            if callable(hook):
                command = hook(artifact, artifact_config, command)
        return command
