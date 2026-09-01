"""Main Project class — primary Python API."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from aimake.cache.store import Cache
from aimake.config.loader import find_config, load_config
from aimake.config.schema import AimakeConfig
from aimake.config.validation import validate_config
from aimake.constants import (
    AIMAKE_DIR,
    BUILD_DIR,
    EXAMPLE_EMBED,
    EXAMPLE_BUILD_INDEX,
    EXAMPLE_EVALUATE,
    EXAMPLE_PREPROCESS,
    EXAMPLE_PROMPT,
    EXAMPLE_REPORT,
    EXAMPLE_TRAIN_DATA,
    INIT_TEMPLATE,
)
from aimake.execution.runner import BuildRunner
from aimake.graph.dag import Graph, GraphError
from aimake.lock import generate_lock, read_lock, write_lock
from aimake.metrics.quality import QualityGateChecker
from aimake.models import ArtifactStatus, BuildPlan, BuildResult, ExplainResult
from aimake.diff.engine import DiffEngine
from aimake.diff.snapshots import extract_snapshot
from aimake.scheduling.resources import GPUDetector


class Project:
    """Primary interface for aimake projects."""

    def __init__(
        self,
        config: AimakeConfig,
        config_path: Path,
        *,
        debug: bool = False,
        verbose: bool = False,
    ) -> None:
        self.config = config
        self.config_path = config_path
        self.project_root = config_path.parent
        self.aimake_dir = self.project_root / AIMAKE_DIR
        self.debug = debug
        self.verbose = verbose

        self.graph = Graph.from_config(config)
        self.cache = Cache(self.aimake_dir, self.project_root, config)
        self._runner: BuildRunner | None = None

    @classmethod
    def load(
        cls,
        path: str | Path | None = None,
        *,
        debug: bool = False,
        verbose: bool = False,
    ) -> Project:
        """Load a project from aimake.yaml."""
        if path:
            config_path = Path(path).resolve()
            config, _ = load_config(config_path)
        else:
            config, config_path = load_config()
        return cls(config, config_path, debug=debug, verbose=verbose)

    @classmethod
    def init(cls, directory: Path | None = None, *, name: str | None = None) -> Path:
        """Initialize a new aimake project."""
        root = (directory or Path.cwd()).resolve()
        project_name = name or root.name

        config_content = INIT_TEMPLATE.format(project_name=project_name)
        config_path = root / "aimake.yaml"
        config_path.write_text(config_content, encoding="utf-8")

        (root / AIMAKE_DIR).mkdir(exist_ok=True)
        (root / BUILD_DIR).mkdir(exist_ok=True)
        (root / "src").mkdir(exist_ok=True)
        (root / "data").mkdir(exist_ok=True)
        (root / "prompts").mkdir(exist_ok=True)

        # Example source files
        (root / "src" / "preprocess.py").write_text(EXAMPLE_PREPROCESS, encoding="utf-8")
        (root / "src" / "embed.py").write_text(EXAMPLE_EMBED, encoding="utf-8")
        (root / "src" / "build_index.py").write_text(EXAMPLE_BUILD_INDEX, encoding="utf-8")
        (root / "src" / "evaluate.py").write_text(EXAMPLE_EVALUATE, encoding="utf-8")
        (root / "src" / "report.py").write_text(EXAMPLE_REPORT, encoding="utf-8")
        (root / "data" / "train.jsonl").write_text(EXAMPLE_TRAIN_DATA, encoding="utf-8")
        (root / "prompts" / "system.txt").write_text(EXAMPLE_PROMPT, encoding="utf-8")

        return config_path

    @property
    def runner(self) -> BuildRunner:
        if self._runner is None:
            self._runner = BuildRunner(
                self.project_root,
                self.config,
                self.graph,
                self.cache,
                jobs=self.config.project.jobs,
                debug=self.debug,
                verbose=self.verbose,
            )
        return self._runner

    def plan(
        self,
        targets: list[str] | None = None,
        *,
        force: list[str] | None = None,
    ) -> BuildPlan:
        """Compute build plan without executing."""
        runner = self._get_runner_for_targets(targets)
        runner.compute_fingerprints()
        runner.compute_statuses(force=set(force or []))
        return runner.plan(force=set(force or []))

    def status(self, targets: list[str] | None = None) -> dict[str, ArtifactStatus]:
        """Get status of all artifacts."""
        runner = self._get_runner_for_targets(targets)
        runner.compute_fingerprints()
        return runner.compute_statuses()

    def build(
        self,
        targets: list[str] | None = None,
        *,
        force: list[str] | None = None,
        dry_run: bool = False,
        jobs: int | None = None,
    ) -> BuildResult:
        """Execute incremental build."""
        runner = self._get_runner_for_targets(targets, jobs=jobs)
        result = runner.build(
            targets=targets,
            force=set(force or []),
            dry_run=dry_run,
        )

        if result.success and not dry_run:
            lock_data = generate_lock(
                self.config.project.name,
                runner.compute_fingerprints(),
            )
            write_lock(self.project_root, lock_data)

        return result

    def explain(self, target: str) -> ExplainResult:
        """Explain why a target is stale."""
        return self.runner.explain(target)

    def clean(
        self,
        *,
        all_cache: bool = False,
        targets: list[str] | None = None,
    ) -> list[str]:
        """Clean build artifacts."""
        return self.runner.clean(all_cache=all_cache, targets=targets)

    def inspect(self, artifact: str) -> dict[str, Any]:
        """Get detailed artifact information."""
        if artifact not in self.graph:
            raise ValueError(f"Unknown artifact: '{artifact}'")

        node = self.graph.get(artifact)
        state = self.cache.get_artifact_state(artifact)
        current_fp = self.runner.compute_fingerprints().get(artifact)

        files = []
        for output in node.config.outputs:
            path = self.project_root / output
            if path.exists():
                if path.is_dir():
                    files.extend(str(p.relative_to(self.project_root)) for p in path.rglob("*") if p.is_file())
                else:
                    files.append(output)
        if node.config.source:
            files.insert(0, node.config.source)

        total_size = sum(
            (self.project_root / f).stat().st_size
            for f in files
            if (self.project_root / f).is_file()
        )

        return {
            "name": artifact,
            "type": node.config.type,
            "status": state.status if state else ArtifactStatus.UNKNOWN,
            "fingerprint": current_fp or (state.fingerprint if state else None),
            "stored_fingerprint": state.fingerprint if state else None,
            "dependencies": node.dependencies,
            "outputs": node.config.outputs,
            "command": node.config.command,
            "created_at": state.created_at if state else None,
            "duration": state.duration if state else None,
            "metrics": state.metrics if state else {},
            "files": files,
            "size_bytes": total_size,
        }

    def graph_dict(self) -> dict[str, Any]:
        """Export graph as dictionary."""
        return self.graph.to_dict()

    def graph_dot(self) -> str:
        """Export graph as DOT format."""
        return self.graph.to_dot()

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get build history."""
        return self.cache.state_db.get_builds(limit)

    def check_quality_gates(self, metrics: dict[str, Any]) -> list:
        """Check metrics against quality gates."""
        checker = QualityGateChecker(self.config)
        numeric = {k: v for k, v in metrics.items() if isinstance(v, (int, float))}
        return checker.check(numeric)

    def diff(self, artifact: str, *, baseline: str = "stored") -> "DiffResult":
        """Diff an artifact against a baseline (stored, lock, or current)."""

        if artifact not in self.graph:
            raise ValueError(f"Unknown artifact: '{artifact}'")

        node = self.graph.get(artifact)
        runner = self.runner
        current_fp = runner.compute_fingerprints().get(artifact)
        baseline_fp: str | None = None
        baseline_label = baseline

        baseline_snapshot: dict | None = None
        if baseline == "stored":
            state = self.cache.get_artifact_state(artifact)
            baseline_fp = state.fingerprint if state else None
            baseline_snapshot = extract_snapshot(state.metadata if state else None)
        elif baseline == "lock":
            lock = read_lock(self.project_root)
            if lock and "artifacts" in lock:
                entry = lock["artifacts"].get(artifact, {})
                baseline_fp = entry.get("fingerprint")
        elif baseline == "current":
            baseline_fp = current_fp
            baseline_label = "current"

        engine = DiffEngine(self.project_root)
        return engine.diff_artifact(
            artifact,
            node.config,
            current_fingerprint=current_fp,
            baseline_fingerprint=baseline_fp,
            baseline_label=baseline_label,
            baseline_snapshot=baseline_snapshot,
        )

    def cache_push(self, fingerprint: str | None = None) -> list[str]:
        """Push local cache entries to remote storage."""
        return self.cache.push_remote(fingerprint)

    def cache_pull(self, fingerprint: str | None = None) -> list[str]:
        """Pull cache entries from remote storage."""
        return self.cache.pull_remote(fingerprint)

    def cache_status(self) -> dict[str, Any]:
        """Return local and remote cache status."""
        return self.cache.remote_status()

    def workers_status(self) -> dict[str, Any]:
        """Return GPU and worker pool status."""
        gpus = GPUDetector.detect()
        pool = self.runner.resource_pool if self._runner else None
        workers = self.runner.worker_pool if self._runner else None
        return {
            "gpus_detected": [
                {"index": g.index, "name": g.name, "memory_mb": g.memory_mb} for g in gpus
            ],
            "gpus_total": pool.total_gpus if pool else len(gpus),
            "gpus_available": pool.available_gpus if pool else len(gpus),
            "workers_enabled": self.config.workers.enabled,
            "workers": workers.list_workers() if workers and workers.enabled else [],
        }

    def doctor(self) -> list[str]:
        """Run project health checks."""
        issues: list[str] = []

        # Python version
        if sys.version_info < (3, 11):
            issues.append(f"ERROR: Python 3.11+ required, found {sys.version}")

        # Config validation
        validation = validate_config(self.config, self.project_root)
        for v in validation:
            issues.append(str(v))

        # Graph cycles
        try:
            Graph.from_config(self.config)
        except GraphError as e:
            issues.append(f"ERROR: {e}")

        # Cache integrity
        corrupted = self.cache.verify_integrity()
        for fp in corrupted:
            issues.append(f"WARNING: Corrupted local cache entry: {fp[:16]}...")

        # Remote cache
        if self.config.cache.remote:
            if not self.cache.remote:
                issues.append("WARNING: Remote cache configured but S3 backend unavailable (install aimake[s3])")
            else:
                status = self.cache.remote_status()
                issues.append(f"OK: Remote cache enabled ({status.get('remote_entries', 0)} entries)")

        # GPU / workers
        gpus = GPUDetector.detect()
        if self.config.project.gpus > 0 or any(
            a.resources.gpu > 0 for a in self.config.artifacts.values()
        ):
            if gpus:
                issues.append(f"OK: {len(gpus)} GPU(s) detected")
            else:
                issues.append("WARNING: GPU resources configured but no GPUs detected")

        if self.config.workers.enabled:
            if not self.config.workers.workers:
                issues.append("ERROR: Workers enabled but none configured")
            else:
                issues.append(f"OK: {len(self.config.workers.workers)} worker(s) configured")

        # Broken artifacts (missing outputs)
        for node in self.graph:
            if node.config.outputs:
                missing = [
                    o for o in node.config.outputs
                    if not (self.project_root / o).exists()
                ]
                state = self.cache.get_artifact_state(node.name)
                if state and state.status == ArtifactStatus.SUCCESS and missing:
                    issues.append(
                        f"WARNING: [{node.name}] Cached but outputs missing: {', '.join(missing)}"
                    )

        if not issues:
            issues.append("OK: All checks passed")

        return issues

    def _get_runner_for_targets(
        self,
        targets: list[str] | None = None,
        jobs: int | None = None,
    ) -> BuildRunner:
        graph = self.graph
        if targets:
            graph = self.graph.subgraph_for_targets(targets)

        return BuildRunner(
            self.project_root,
            self.config,
            graph,
            self.cache,
            jobs=jobs or self.config.project.jobs,
            debug=self.debug,
            verbose=self.verbose,
        )

    def close(self) -> None:
        self.cache.close()
