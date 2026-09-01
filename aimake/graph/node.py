"""Graph node representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aimake.config.schema import ArtifactConfig


@dataclass
class Node:
    """A node in the dependency DAG representing one artifact."""

    name: str
    config: ArtifactConfig
    dependencies: list[str] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)

    @property
    def artifact_type(self) -> str:
        return self.config.type

    @property
    def is_passive(self) -> bool:
        """Passive artifacts have a source but no command."""
        return bool(self.config.source) and not self.config.command

    @property
    def is_active(self) -> bool:
        return bool(self.config.command)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.config.type,
            "dependencies": self.dependencies,
            "dependents": self.dependents,
            "source": self.config.source,
            "command": self.config.command,
            "outputs": self.config.outputs,
        }
