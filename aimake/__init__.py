"""aimake — incremental build system for AI applications."""

import aimake.artifacts  # noqa: F401 — register artifact types

from aimake.artifacts.base import Artifact
from aimake.cache.store import Cache
from aimake.diff.engine import DiffEngine
from aimake.graph.dag import Graph
from aimake.hashing.fingerprint import Fingerprinter
from aimake.models import ArtifactState, ArtifactStatus, BuildResult
from aimake.project import Project

__version__ = "1.3.0"

__all__ = [
    "Artifact",
    "ArtifactState",
    "ArtifactStatus",
    "BuildResult",
    "Cache",
    "DiffEngine",
    "Fingerprinter",
    "Graph",
    "Project",
    "__version__",
]
