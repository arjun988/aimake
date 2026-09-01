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


class SearchParamConfig(BaseModel):
    """Hyperparameter search space definition."""

    type: str = "float"  # float, int, categorical
    low: float | None = None
    high: float | None = None
    step: float | None = None
    choices: list[Any] | None = None

    @model_validator(mode="after")
    def validate_search_param(self) -> SearchParamConfig:
        if self.type == "categorical":
            if not self.choices:
                raise ValueError("Categorical search params require 'choices'")
        elif self.low is None or self.high is None:
            raise ValueError(f"Search param type '{self.type}' requires 'low' and 'high'")
        elif self.low > self.high:
            raise ValueError("Search param 'low' must be <= 'high'")
        return self


class ObjectiveConfig(BaseModel):
    """Optimization objective (single- or multi-metric)."""

    metric: str | None = None
    metrics: list[str] | None = None
    direction: str = "maximize"  # maximize | minimize (single-objective default)
    directions: list[str] | None = None  # per-metric directions for multi-objective
    artifact: str | None = None  # artifact with metrics; auto-detected if omitted

    @field_validator("direction")
    @classmethod
    def normalize_direction(cls, v: str) -> str:
        v = v.lower()
        if v not in ("maximize", "minimize"):
            raise ValueError("Objective direction must be 'maximize' or 'minimize'")
        return v

    @field_validator("directions")
    @classmethod
    def normalize_directions(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        normalized = []
        for item in v:
            item = item.lower()
            if item not in ("maximize", "minimize"):
                raise ValueError("Objective directions must be 'maximize' or 'minimize'")
            normalized.append(item)
        return normalized

    @model_validator(mode="after")
    def validate_objectives(self) -> ObjectiveConfig:
        if not self.metric and not self.metrics:
            raise ValueError("Objective requires 'metric' or 'metrics'")
        if self.metrics and self.directions and len(self.directions) != len(self.metrics):
            raise ValueError("'directions' length must match 'metrics'")
        return self

    def is_multi_objective(self) -> bool:
        return bool(self.metrics and len(self.metrics) > 1)

    def metric_names(self) -> list[str]:
        if self.metrics:
            return list(self.metrics)
        assert self.metric is not None
        return [self.metric]

    def metric_directions(self) -> dict[str, str]:
        if self.metrics and self.directions:
            return dict(zip(self.metrics, self.directions, strict=True))
        if self.metrics:
            return {name: self.direction for name in self.metrics}
        assert self.metric is not None
        return {self.metric: self.direction}


class EarlyStoppingConfig(BaseModel):
    """Stop optimization when progress stalls."""

    enabled: bool = False
    patience: int = 3
    min_trials: int = 2
    min_delta: float = 0.0

    @model_validator(mode="after")
    def validate_early_stopping(self) -> EarlyStoppingConfig:
        if self.patience < 1:
            raise ValueError("early_stopping.patience must be >= 1")
        if self.min_trials < 1:
            raise ValueError("early_stopping.min_trials must be >= 1")
        return self


class MLflowConfig(BaseModel):
    """MLflow experiment tracking export."""

    enabled: bool = False
    tracking_uri: str | None = None
    experiment_name: str | None = None
    registry_uri: str | None = None


class OptimizationConfig(BaseModel):
    """Automatic hyperparameter optimization."""

    trials: int = 5
    strategy: str = "grid"  # grid | random | bayesian | optuna
    parameter_artifact: str | None = None
    search_space: dict[str, SearchParamConfig] = Field(default_factory=dict)
    objective: ObjectiveConfig | None = None
    early_stopping: EarlyStoppingConfig | None = None
    mlflow: MLflowConfig | None = None
    seed: int | None = None

    @field_validator("strategy")
    @classmethod
    def normalize_strategy(cls, v: str) -> str:
        v = v.lower()
        if v not in ("grid", "random", "bayesian", "optuna"):
            raise ValueError(
                "Optimization strategy must be 'grid', 'random', 'bayesian', or 'optuna'"
            )
        return v

    @model_validator(mode="after")
    def validate_optimization(self) -> OptimizationConfig:
        if not self.search_space:
            raise ValueError("Optimization requires a non-empty 'search_space'")
        if self.objective is None:
            raise ValueError("Optimization requires an 'objective' block")
        if self.trials < 1:
            raise ValueError("Optimization trials must be >= 1")
        return self


class AimakeConfig(BaseModel):
    """Root configuration model for aimake.yaml."""

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    artifacts: dict[str, ArtifactConfig] = Field(default_factory=dict)
    quality_gates: dict[str, QualityGateConfig] = Field(default_factory=dict)
    environment: list[str] = Field(default_factory=list)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    workers: WorkersConfig = Field(default_factory=WorkersConfig)
    optimization: OptimizationConfig | None = None

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
