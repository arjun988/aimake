"""aimake — incremental build system for AI applications."""

import aimake.artifacts  # noqa: F401 — register artifact types

from aimake.artifacts.base import Artifact
from aimake.cache.store import Cache
from aimake.diff.engine import DiffEngine
from aimake.graph.dag import Graph
from aimake.hashing.fingerprint import Fingerprinter
from aimake.models import ArtifactState, ArtifactStatus, BuildResult
from aimake.project import Project
from aimake.sdk import Aimake, load

__version__ = "1.7.0"

__all__ = [
    "Aimake",
    "Artifact",
    "ArtifactState",
    "ArtifactStatus",
    "BuildResult",
    "Cache",
    "DiffEngine",
    "Fingerprinter",
    "Graph",
    "Project",
    "load",
    "__version__",
]
