"""Artifact fingerprint computation."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

from aimake.config.schema import AimakeConfig, ArtifactConfig
from aimake.constants import HASH_PREFIX, SECRET_REDACTED
from aimake.graph.dag import Graph
from aimake.hashing.directories import expand_glob, hash_directory, hash_inputs
from aimake.hashing.file_cache import FileHashCache
from aimake.hashing.files import hash_file, hash_string


class Fingerprinter:
    """Compute deterministic fingerprints for artifacts."""

    def __init__(
        self,
        project_root: Path,
        config: AimakeConfig,
        graph: Graph,
        *,
        debug: bool = False,
        file_cache: FileHashCache | None = None,
    ) -> None:
        self.project_root = project_root
        self.config = config
        self.graph = graph
        self.debug = debug
        self.file_cache = file_cache
        self._file_hash_cache: dict[str, str] = {}
        self._computed: dict[str, str] = {}

    def fingerprint_all(self) -> dict[str, str]:
        """Compute fingerprints for all artifacts in topological order."""
        self._computed.clear()
        for node in self.graph:
            self._computed[node.name] = self.fingerprint(node.name)
        return dict(self._computed)

    def fingerprint(self, name: str) -> str:
        """Compute fingerprint for a single artifact."""
        if name in self._computed:
            return self._computed[name]

        node = self.graph.get(name)
        artifact = node.config
        parts: list[str] = []

        # Artifact identity
        parts.append(f"name:{name}")
        parts.append(f"type:{artifact.type}")

        # Source content
        if artifact.source:
            source_path = self.project_root / artifact.source
            if source_path.is_file():
                parts.append(f"source:{self._cached_file_hash(source_path)}")
            elif source_path.is_dir():
                parts.append(f"source_dir:{hash_directory(source_path)}")

        # Declared inputs
        if artifact.inputs:
            parts.append(f"inputs:{hash_inputs(artifact.inputs, self.project_root)}")

        # Command
        if artifact.command:
            parts.append(f"command:{artifact.command}")

        # Outputs declaration (affects invalidation if outputs list changes)
        if artifact.outputs:
            parts.append(f"outputs:{json.dumps(sorted(artifact.outputs), sort_keys=True)}")

        # Parameters
        if artifact.parameters:
            parts.append(f"parameters:{json.dumps(artifact.parameters, sort_keys=True)}")

        # Metadata
        if artifact.metadata:
            parts.append(f"metadata:{json.dumps(artifact.metadata, sort_keys=True)}")

        # Environment variables (names + redacted values for secrets)
        env_vars = list(set(self.config.environment + artifact.environment))
        if env_vars:
            env_parts = []
            for var in sorted(env_vars):
                value = os.environ.get(var, "")
                # Redact likely secrets
                if any(s in var.upper() for s in ("KEY", "SECRET", "TOKEN", "PASSWORD")):
                    env_parts.append(f"{var}={SECRET_REDACTED}")
                else:
                    env_parts.append(f"{var}={value}")
            parts.append(f"environment:{';'.join(env_parts)}")

        # Dependency fingerprints
        for dep in sorted(node.dependencies):
            dep_fp = self.fingerprint(dep)
            parts.append(f"dep:{dep}:{dep_fp}")

        # Type-specific extras
        type_hash = self._type_specific_hash(name, artifact)
        if type_hash:
            parts.append(type_hash)

        combined = "\n".join(parts)
        result = hash_string(combined)
        self._computed[name] = result

        if self.debug:
            print(f"[debug] fingerprint {name}: {result}")
            for part in parts:
                print(f"  {part[:120]}")

        return result

    def _cached_file_hash(self, path: Path) -> str:
        key = str(path.resolve())
        if key in self._file_hash_cache:
            return self._file_hash_cache[key]
        if self.file_cache is not None:
            self._file_hash_cache[key] = self.file_cache.hash_file(path)
        elif path.is_file():
            self._file_hash_cache[key] = hash_file(path)
        else:
            self._file_hash_cache[key] = hash_string("missing")
        return self._file_hash_cache[key]

    def _type_specific_hash(self, name: str, artifact: ArtifactConfig) -> str:
        """Add type-specific fingerprint components."""
        if artifact.type == "dataset" and artifact.source:
            return self._dataset_hash(artifact)
        if artifact.type == "prompt" and artifact.source:
            return self._prompt_hash(artifact)
        if artifact.type == "model":
            return self._model_hash(artifact)
        if artifact.type == "evaluation" and artifact.metrics:
            return f"metrics_file:{artifact.metrics.file}"
        return ""

    def _dataset_hash(self, artifact: ArtifactConfig) -> str:
        source = self.project_root / (artifact.source or "")
        if not source.exists():
            return "dataset:missing"
        info: dict[str, Any] = {"path": artifact.source}
        if source.is_file():
            info["hash"] = self._cached_file_hash(source)
            info["size"] = source.stat().st_size
            if source.suffix in (".jsonl", ".csv", ".tsv"):
                try:
                    with open(source, encoding="utf-8") as f:
                        info["rows"] = sum(1 for line in f if line.strip())
                except OSError:
                    pass
        elif source.is_dir():
            info["hash"] = hash_directory(source)
        return f"dataset:{json.dumps(info, sort_keys=True)}"

    def _prompt_hash(self, artifact: ArtifactConfig) -> str:
        source = self.project_root / (artifact.source or "")
        if source.is_file():
            content = source.read_text(encoding="utf-8")
            return f"prompt:{hash_string(content)}"
        return "prompt:missing"

    def _model_hash(self, artifact: ArtifactConfig) -> str:
        parts = []
        if artifact.source:
            source = self.project_root / artifact.source
            if source.is_file():
                parts.append(self._cached_file_hash(source))
        if artifact.parameters:
            parts.append(json.dumps(artifact.parameters, sort_keys=True))
        return f"model:{hash_string('|'.join(parts))}"

    @staticmethod
    def environment_fingerprint() -> str:
        """Fingerprint the build environment for reproducibility metadata."""
        info = {
            "python": sys.version,
            "platform": platform.platform(),
            "architecture": platform.machine(),
        }
        return hash_string(json.dumps(info, sort_keys=True))

    def explain_diff(
        self,
        name: str,
        old_fp: str,
        new_fp: str,
    ) -> str:
        """Explain what changed between two fingerprints."""
        if old_fp == new_fp:
            return "Fingerprints are identical — artifact is up to date."

        node = self.graph.get(name)
        reasons: list[str] = []

        # Check source changes
        if node.config.source:
            source = self.project_root / node.config.source
            if source.is_file():
                reasons.append(f"Source file '{node.config.source}' may have changed")

        # Check dependency changes
        for dep in node.dependencies:
            reasons.append(f"Dependency '{dep}' may have changed")

        if node.config.command:
            reasons.append("Command or its inputs may have changed")

        if not reasons:
            reasons.append("Configuration or environment may have changed")

        return "; ".join(reasons)
