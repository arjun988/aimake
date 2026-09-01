"""Artifact types package — import all to register types."""

from aimake.artifacts.base import Artifact, ArtifactRegistry, GenericArtifact
from aimake.artifacts.dataset import DatasetArtifact
from aimake.artifacts.embedding import EmbeddingArtifact
from aimake.artifacts.evaluation import EvaluationArtifact
from aimake.artifacts.model import ModelArtifact
from aimake.artifacts.prompt import PromptArtifact
from aimake.artifacts.report import ReportArtifact
from aimake.artifacts.vector_index import VectorIndexArtifact

__all__ = [
    "Artifact",
    "ArtifactRegistry",
    "DatasetArtifact",
    "EmbeddingArtifact",
    "EvaluationArtifact",
    "GenericArtifact",
    "ModelArtifact",
    "PromptArtifact",
    "ReportArtifact",
    "VectorIndexArtifact",
]
