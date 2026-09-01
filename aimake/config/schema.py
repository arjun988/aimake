"""Configuration schema using Pydantic."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class ProjectConfig(BaseModel):
    """Top-level project metadata."""

    name: str = "my-ai-project"
    version: str = "1.0"
    jobs: int = 0
    gpus: int = 0  # 0 = auto-detect local GPUs


class ResourceConfig(BaseModel):
    """Compute resources required by an artifact."""

    gpu: int = 0
    memory_gb: float = 0


class MetricsConfig(BaseModel):
    """Configuration for parsing evaluation metrics."""

    file: str | None = None


class ArtifactConfig(BaseModel):
    """Configuration for a single artifact in the pipeline."""

    type: str = "generic"
    source: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    command: str | None = None
    outputs: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    environment: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    metrics: MetricsConfig | None = None
    resources: ResourceConfig = Field(default_factory=ResourceConfig)
    worker: str | None = None

    @field_validator("type")
    @classmethod
    def normalize_type(cls, v: str) -> str:
        from aimake.constants import ARTIFACT_TYPE_ALIASES, ARTIFACT_TYPES

        canonical = ARTIFACT_TYPE_ALIASES.get(v, v)
        if canonical not in ARTIFACT_TYPES and v not in ARTIFACT_TYPES:
            raise ValueError(
                f"Unknown artifact type '{v}'. "
                f"Valid types: {', '.join(sorted(ARTIFACT_TYPES))}"
            )
        return canonical if canonical in ARTIFACT_TYPES else v

    @model_validator(mode="after")
    def validate_artifact(self) -> ArtifactConfig:
        has_command = bool(self.command)
        has_source = bool(self.source)
        if not has_command and not has_source:
            raise ValueError(
                "Artifact must have either 'source' (passive) or 'command' (active)"
            )
        if has_command and not self.outputs and self.type not in ("prompt", "dataset", "model"):
            # Passive source-only types don't need outputs; active commands do
            pass
        return self


class QualityGateConfig(BaseModel):
    """Quality gate threshold for a metric."""

    minimum: float | None = None
    maximum: float | None = None


class S3CacheConfig(BaseModel):
    """S3 remote cache configuration."""

    bucket: str
    prefix: str = "aimake/cache/"
    region: str | None = None
    endpoint_url: str | None = None


class RemoteCacheConfig(BaseModel):
    """Remote cache settings."""

    type: str = "s3"
    s3: S3CacheConfig | None = None
    auto_pull: bool = True
    auto_push: bool = True

    @model_validator(mode="after")
    def validate_remote(self) -> RemoteCacheConfig:
        if self.type == "s3" and self.s3 is None:
            raise ValueError("Remote cache type 's3' requires an 's3' configuration block")
        return self


class CacheConfig(BaseModel):
    """Cache configuration."""

    remote: RemoteCacheConfig | None = None


class WorkerConfig(BaseModel):
    """Remote build worker."""

    name: str
    host: str
    user: str | None = None
    gpus: int = 0
    jobs: int = 1
    workdir: str | None = None
    ssh_options: list[str] = Field(default_factory=list)


class WorkersConfig(BaseModel):
    """Distributed worker pool."""

    enabled: bool = False
    workers: list[WorkerConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_workers(self) -> WorkersConfig:
        names = [w.name for w in self.workers]
        if len(names) != len(set(names)):
            raise ValueError("Worker names must be unique")
        return self


class AimakeConfig(BaseModel):
    """Root configuration model for aimake.yaml."""

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    artifacts: dict[str, ArtifactConfig] = Field(default_factory=dict)
    quality_gates: dict[str, QualityGateConfig] = Field(default_factory=dict)
    environment: list[str] = Field(default_factory=list)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    workers: WorkersConfig = Field(default_factory=WorkersConfig)

    @model_validator(mode="after")
    def validate_artifacts(self) -> AimakeConfig:
        if not self.artifacts:
            raise ValueError("Configuration must define at least one artifact")
        names = set(self.artifacts.keys())
        for name, artifact in self.artifacts.items():
            for dep in artifact.depends_on:
                if dep not in names:
                    raise ValueError(
                        f"Artifact '{name}' depends on unknown artifact '{dep}'"
                    )
                if dep == name:
                    raise ValueError(f"Artifact '{name}' cannot depend on itself")
        return self
