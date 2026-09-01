"""Base artifact class and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from aimake.config.schema import ArtifactConfig


class Artifact(ABC):
    """Base class for all artifact types."""

    artifact_type: ClassVar[str] = "generic"

    def __init__(self, name: str, config: ArtifactConfig, project_root: Path) -> None:
        self.name = name
        self.config = config
        self.project_root = project_root

    @property
    def dependencies(self) -> list[str]:
        return list(self.config.depends_on)

    @property
    def outputs(self) -> list[str]:
        return list(self.config.outputs)

    @property
    def command(self) -> str | None:
        return self.config.command

    @property
    def source(self) -> str | None:
        return self.config.source

    @abstractmethod
    def collect_metadata(self) -> dict[str, Any]:
        """Collect type-specific metadata for storage."""

    def validate(self) -> list[str]:
        """Validate artifact configuration. Returns list of errors."""
        errors: list[str] = []
        if self.config.source:
            path = self.project_root / self.config.source
            if not path.exists():
                errors.append(f"Source not found: {self.config.source}")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.artifact_type,
            "dependencies": self.dependencies,
            "outputs": self.outputs,
            "command": self.command,
            "source": self.source,
            "parameters": self.config.parameters,
            "metadata": self.collect_metadata(),
        }


class GenericArtifact(Artifact):
    artifact_type = "generic"

    def collect_metadata(self) -> dict[str, Any]:
        return dict(self.config.metadata)


class ArtifactRegistry:
    """Registry for artifact type implementations."""

    _types: dict[str, type[Artifact]] = {}

    @classmethod
    def register(cls, artifact_cls: type[Artifact]) -> type[Artifact]:
        cls._types[artifact_cls.artifact_type] = artifact_cls
        return artifact_cls

    @classmethod
    def create(
        cls,
        name: str,
        config: ArtifactConfig,
        project_root: Path,
    ) -> Artifact:
        artifact_cls = cls._types.get(config.type, GenericArtifact)
        return artifact_cls(name, config, project_root)

    @classmethod
    def registered_types(cls) -> list[str]:
        return sorted(cls._types.keys())
