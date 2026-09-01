"""Build execution orchestration."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from aimake.cache.store import Cache
from aimake.config.schema import AimakeConfig
from aimake.execution.process import ExecutionError, ProcessRunner
from aimake.execution.scheduler import BuildScheduler, ScheduleResult
from aimake.graph.dag import Graph
from aimake.graph.planner import Planner
from aimake.diff.snapshots import capture_snapshot, extract_snapshot, merge_metadata_with_snapshot
from aimake.hashing.file_cache import FileHashCache
from aimake.hashing.fingerprint import Fingerprinter
from aimake.metrics.parser import MetricsParser
from aimake.models import (
    ArtifactStatus,
    BuildAction,
    BuildPlan,
    BuildResult,
    ExplainResult,
)
from aimake.state.database import StateDatabase
from aimake.scheduling.resources import ResourcePool
from aimake.scheduling.workers import WorkerPool
from aimake.plugins.base import PluginManager


class BuildRunner:
    """Orchestrate incremental builds."""

    def __init__(
        self,
        project_root: Path,
        config: AimakeConfig,
        graph: Graph,
        cache: Cache,
        *,
        jobs: int = 0,
        debug: bool = False,
        verbose: bool = False,
        plugin_manager: PluginManager | None = None,
    ) -> None:
        self.project_root = project_root
        self.config = config
        self.graph = graph
        self.cache = cache
        self.jobs = jobs or config.project.jobs
        self.debug = debug
        self.verbose = verbose
        self.plugin_manager = plugin_manager or PluginManager()

        self.resource_pool = ResourcePool(config.project.gpus)
        self.worker_pool = WorkerPool(config.workers)
        self.file_cache = FileHashCache(cache.state_db)

        self.fingerprinter = Fingerprinter(
            project_root, config, graph, debug=debug, file_cache=self.file_cache
        )
        self.planner = Planner(graph)
        self.process = ProcessRunner(project_root, debug=debug)
        self.scheduler = BuildScheduler(
            graph,
            jobs=self.jobs,
            resource_pool=self.resource_pool,
            worker_pool=self.worker_pool,
        )
        self.metrics_parser = MetricsParser(project_root)
        self.db: StateDatabase = cache.state_db

        self._fingerprints: dict[str, str] = {}
        self._statuses: dict[str, ArtifactStatus] = {}
        self._build_id: int | None = None
        self._build_parameters: dict[str, Any] = {}
        self._fidelity_level: int | None = None
        self._max_fidelity: int | None = None
        self._fidelity_env: dict[str, str] = {}
        self._log_path: Path | None = None
        self._log_lines: list[str] = []

    def compute_fingerprints(self, *, targets: list[str] | None = None) -> dict[str, str]:
        if targets:
            graph = self.graph.subgraph_for_targets(targets)
            fingerprinter = Fingerprinter(
                self.project_root,
                self.config,
                graph,
                debug=self.debug,
                file_cache=self.file_cache,
            )
            self._fingerprints = fingerprinter.fingerprint_all()
        else:
            self._fingerprints = self.fingerprinter.fingerprint_all()
        return self._fingerprints

    def compute_statuses(
        self,
        *,
        force: set[str] | None = None,
        targets: list[str] | None = None,
    ) -> dict[str, ArtifactStatus]:
        if not self._fingerprints:
            self.compute_fingerprints(targets=targets)
        graph = self.graph
        if targets:
            graph = self.graph.subgraph_for_targets(targets)
        stored = self.cache.get_stored_fingerprints()
        outputs_exist = self._check_outputs_exist(graph)
        self._statuses = self.planner.compute_statuses(
            self._fingerprints,
            stored,
            graph,
            outputs_exist=outputs_exist,
            force=force,
        )
        return self._statuses

    def plan(
        self,
        *,
        force: set[str] | None = None,
        targets: list[str] | None = None,
    ) -> BuildPlan:
        graph = self.graph
        planner = self.planner
        if targets:
            graph = self.graph.subgraph_for_targets(targets)
            planner = Planner(graph)
        if not self._fingerprints or targets:
            self.compute_fingerprints(targets=targets)
        if not self._statuses or targets:
            self.compute_statuses(force=force, targets=targets)
        return planner.plan(self._statuses, force=force)

    def explain(self, target: str) -> ExplainResult:
        if target not in self.graph:
            raise ValueError(f"Unknown artifact: '{target}'")

        if not self._fingerprints:
            self.compute_fingerprints()
        if not self._statuses:
            self.compute_statuses()

        status = self._statuses.get(target, ArtifactStatus.UNKNOWN)
        stored = self.cache.get_stored_fingerprints()
        current_fp = self._fingerprints.get(target, "")
        stored_fp = stored.get(target, "")

        chain: list[str] = []
        root_cause = ""
        old_fp: str | None = stored_fp or None
        new_fp: str | None = current_fp or None

        if status in (ArtifactStatus.UP_TO_DATE, ArtifactStatus.CACHED):
            return ExplainResult(
                target=target,
                conclusion=f"{target} is up to date — no rebuild needed.",
            )

        # Walk dependency chain to find root cause
        def find_cause(name: str, visited: set[str]) -> str | None:
            if name in visited:
                return None
            visited.add(name)

            node = self.graph.get(name)
            current = self._fingerprints.get(name, "")
            stored_f = stored.get(name, "")

            if current != stored_f and stored_f:
                return name
            if not stored_f:
                if node.config.source:
                    source = self.project_root / node.config.source
                    if source.exists():
                        return name
                if not node.dependencies:
                    return name

            for dep in node.dependencies:
                cause = find_cause(dep, visited)
                if cause:
                    return cause
            return name if current != stored_f else None

        cause = find_cause(target, set())
        if cause:
            chain = self._build_chain(cause, target)
            root_cause = f"{cause} changed"
            old_fp = stored.get(cause)
            new_fp = self._fingerprints.get(cause)

        conclusion = f"Therefore: {target} must be rebuilt."
        if status == ArtifactStatus.CHANGED:
            conclusion = f"{target}'s own inputs changed. {conclusion}"
        elif cause and cause != target:
            conclusion = (
                f"{target} depends on {cause}. "
                f"{cause} changed. {conclusion}"
            )

        return ExplainResult(
            target=target,
            chain=chain,
            root_cause=root_cause,
            old_fingerprint=old_fp,
            new_fingerprint=new_fp,
            conclusion=conclusion,
        )

    def _build_chain(self, start: str, end: str) -> list[str]:
        """Build dependency chain from start to end."""
        # BFS from end to start through dependencies
        chain = [end]
        current = end
        visited = {end}
        while current != start:
            node = self.graph.get(current)
            found = False
            for dep in node.dependencies:
                if dep == start or dep in self.graph.ancestors(start):
                    chain.append(dep)
                    current = dep
                    found = True
                    break
            if not found:
                if node.dependencies:
                    dep = node.dependencies[0]
                    if dep not in visited:
                        chain.append(dep)
                        current = dep
                        visited.add(dep)
                    else:
                        break
                else:
                    break
            if current == start:
                break
        chain.reverse()
        if start not in chain:
            chain.insert(0, start)
        return chain

    def build(
        self,
        targets: list[str] | None = None,
        *,
        force: set[str] | None = None,
        dry_run: bool = False,
        build_parameters: dict[str, Any] | None = None,
        experiment_id: int | None = None,
        trial_number: int | None = None,
        fidelity_level: int | None = None,
        max_fidelity: int | None = None,
        fidelity_env: dict[str, str] | None = None,
    ) -> BuildResult:
        """Execute incremental build."""
        import time

        from aimake.git.integration import get_git_info

        start_time = time.monotonic()
        self._build_parameters = dict(build_parameters or {})
        self._fidelity_level = fidelity_level
        self._max_fidelity = max_fidelity
        self._fidelity_env = dict(fidelity_env or {})

        # Expand force to include all downstream dependents
        if force:
            expanded: set[str] = set(force)
            for name in force:
                if name in self.graph:
                    expanded.update(self.graph.descendants(name))
            force = expanded

        # Subgraph for targeted builds
        graph = self.graph
        if targets:
            graph = self.graph.subgraph_for_targets(targets)

        self.fingerprinter = Fingerprinter(
            self.project_root, self.config, graph, debug=self.debug, file_cache=self.file_cache
        )
        self.planner = Planner(graph)
        self.scheduler = BuildScheduler(
            graph,
            jobs=self.jobs,
            resource_pool=self.resource_pool,
            worker_pool=self.worker_pool,
        )

        self._resolve_missing_hf_sources(graph)
        self.compute_fingerprints()
        plan = self.plan(force=force)

        if dry_run:
            return BuildResult(
                build_id=0,
                success=True,
                duration=0,
                rebuilt=plan.to_run,
                reused=plan.to_skip + plan.to_restore,
            )

        import threading

        git_info = get_git_info(self.project_root)
        self._build_id = self.db.start_build(
            git_info,
            parameters=self._build_parameters or None,
            experiment_id=experiment_id,
            trial_number=trial_number,
        )
        self._setup_log()
        self._emit_plugins(
            "on_build_start",
            {
                "project_root": self.project_root,
                "build_id": self._build_id,
                "graph": graph,
            },
        )

        rebuilt: list[str] = []
        reused: list[str] = []
        failed: list[str] = []
        changed: list[str] = []
        result_lock = threading.Lock()

        stored = self.cache.get_stored_fingerprints()

        def run_artifact(name: str) -> ScheduleResult:
            entry = next(e for e in plan.entries if e.name == name)
            node = graph.get(name)
            fp = self._fingerprints[name]

            try:
                if entry.action == BuildAction.SKIP:
                    with result_lock:
                        reused.append(name)
                    return ScheduleResult(name=name, success=True)

                if entry.action == BuildAction.RESTORE:
                    if self.cache.restore(name, fp, node.config.outputs):
                        self._log(f"RESTORED {name} from cache")
                        with result_lock:
                            reused.append(name)
                        return ScheduleResult(name=name, success=True)

                self._emit_plugins(
                    "on_pre_artifact",
                    self._artifact_context(
                        name,
                        node,
                        fp,
                        graph,
                        rebuilding=entry.action == BuildAction.RUN,
                    ),
                )

                # Run command for passive source artifacts or active commands
                if node.is_passive:
                    metadata = self._build_metadata(node)
                    self._handle_passive(node, fp, metadata=metadata)
                    self._emit_plugins(
                        "on_artifact_complete",
                        self._artifact_context(
                            name,
                            node,
                            fp,
                            graph,
                            success=True,
                            metadata=metadata,
                        ),
                    )
                    self._maybe_register_artifact(name, fp, metadata=metadata)
                elif node.config.command:
                    gpu_indices: list[int] = []
                    worker_state = None
                    worker_cfg = None
                    gpu_needed = node.config.resources.gpu
                    extra_env: dict[str, str] = {}
                    extra_env.update(self._parameter_env(node))

                    try:
                        if gpu_needed > 0:
                            gpu_indices = self.resource_pool.acquire(gpu_needed, name) or []
                            if len(gpu_indices) < gpu_needed:
                                raise ExecutionError(
                                    name,
                                    node.config.command,
                                    0,
                                    f"Not enough GPUs available (need {gpu_needed})",
                                )
                            extra_env.update(self.resource_pool.gpu_env(gpu_indices))

                        if self.worker_pool.enabled:
                            worker_state = self.worker_pool.select_worker(
                                worker_name=node.config.worker,
                                gpu_required=gpu_needed,
                            )
                            if node.config.worker and worker_state is None:
                                raise ExecutionError(
                                    name,
                                    node.config.command,
                                    0,
                                    f"Worker '{node.config.worker}' unavailable",
                                )
                            if worker_state:
                                if not self.worker_pool.acquire(worker_state, gpu_needed):
                                    raise ExecutionError(
                                        name,
                                        node.config.command,
                                        0,
                                        f"Worker '{worker_state.config.name}' at capacity",
                                    )
                                worker_cfg = worker_state.config

                        record = self.process.run(
                            name,
                            node.config.command,
                            env_vars=list(
                                set(self.config.environment + node.config.environment)
                            ),
                            extra_env=extra_env or None,
                            worker=worker_cfg,
                        )
                    finally:
                        if gpu_indices:
                            self.resource_pool.release(gpu_indices)
                        if worker_state:
                            self.worker_pool.release(worker_state, gpu_needed)

                    self._log(record.stdout)
                    if record.stderr and self.verbose:
                        self._log(record.stderr)

                    missing = self.process.validate_outputs(
                        node.config.outputs, self.project_root
                    )
                    if missing:
                        raise ExecutionError(
                            name,
                            node.config.command,
                            0,
                            f"Expected output does not exist: {', '.join(missing)}",
                        )

                    self.db.log_execution(
                        self._build_id,
                        name,
                        node.config.command,
                        record.exit_code,
                        record.stdout,
                        record.stderr,
                        record.start_time,
                        record.end_time,
                        record.duration,
                    )

                    metrics = self._parse_metrics(node)
                    metadata = self._build_metadata(node)
                    self.cache.store(
                        name,
                        fp,
                        artifact_type=node.config.type,
                        command=node.config.command,
                        outputs=node.config.outputs,
                        duration=record.duration,
                        metadata=metadata,
                        metrics=metrics,
                    )
                    self._emit_plugins(
                        "on_artifact_complete",
                        self._artifact_context(
                            name,
                            node,
                            fp,
                            graph,
                            success=True,
                            metadata=metadata,
                            metrics=metrics,
                            duration=record.duration,
                        ),
                    )
                    self._maybe_register_artifact(name, fp, metadata=metadata, metrics=metrics)
                else:
                    metadata = self._build_metadata(node)
                    self.cache.store(
                        name,
                        fp,
                        artifact_type=node.config.type,
                        outputs=node.config.outputs,
                        metadata=metadata,
                    )
                    self._emit_plugins(
                        "on_artifact_complete",
                        self._artifact_context(
                            name,
                            node,
                            fp,
                            graph,
                            success=True,
                            metadata=metadata,
                        ),
                    )

                if stored.get(name) != fp:
                    with result_lock:
                        changed.append(name)
                with result_lock:
                    rebuilt.append(name)
                self._log(f"BUILT {name}")
                return ScheduleResult(name=name, success=True)

            except ExecutionError as e:
                with result_lock:
                    failed.append(name)
                self._log(f"FAILED {name}: {e.stderr}")
                return ScheduleResult(name=name, success=False, error=e.stderr)
            except Exception as e:
                with result_lock:
                    failed.append(name)
                self._log(f"FAILED {name}: {e}")
                return ScheduleResult(name=name, success=False, error=str(e))

        # Handle skip entries
        for entry in plan.entries:
            if entry.action == BuildAction.SKIP:
                reused.append(entry.name)

        # Execute run/restore entries
        run_entries = [e for e in plan.entries if e.action != BuildAction.SKIP]
        if run_entries:
            run_plan = BuildPlan(entries=run_entries)
            results = self.scheduler.execute(run_plan, run_artifact)
            for r in results:
                if not r.success and r.name not in failed:
                    failed.append(r.name)

        duration = time.monotonic() - start_time
        success = len(failed) == 0

        # Collect metrics from evaluation artifacts
        all_metrics: dict[str, Any] = {}
        for name in rebuilt:
            state = self.cache.get_artifact_state(name)
            if state and state.metrics:
                all_metrics.update(state.metrics)

        if self._build_id:
            self.db.finish_build(
                self._build_id,
                duration=duration,
                status="success" if success else "failed",
                changed=changed,
                rebuilt=rebuilt,
                reused=reused,
                failed=failed,
                metrics=all_metrics,
            )

        build_result = BuildResult(
            build_id=self._build_id or 0,
            success=success,
            duration=duration,
            rebuilt=rebuilt,
            reused=reused,
            failed=failed,
            changed_artifacts=changed,
            metrics=all_metrics,
            git_commit=git_info.commit if git_info.available else None,
            git_branch=git_info.branch if git_info.available else None,
            git_dirty=git_info.dirty if git_info.available else None,
        )
        self._emit_plugins(
            "on_build_finish",
            {
                "project_root": self.project_root,
                "build_id": self._build_id,
                "result": build_result,
            },
        )

        self._finalize_log()

        return build_result

    def _emit_plugins(self, event: str, context: dict[str, Any]) -> None:
        if self.plugin_manager.plugins:
            self.plugin_manager.emit(event, context)

    def _artifact_context(
        self,
        name: str,
        node,
        fingerprint: str,
        graph: Graph,
        *,
        rebuilding: bool = False,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        duration: float | None = None,
    ) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "artifact": name,
            "artifact_config": node.config,
            "artifact_type": node.config.type,
            "fingerprint": fingerprint,
            "build_id": self._build_id,
            "rebuilding": rebuilding,
            "success": success,
            "metadata": metadata or {},
            "metrics": metrics or {},
            "duration": duration,
            "outputs": list(node.config.outputs),
            "graph": graph,
        }

    def _resolve_missing_hf_sources(self, graph: Graph) -> None:
        """Pull Hub assets when local source paths are missing."""
        hf_plugin = self.plugin_manager.get("huggingface")
        if hf_plugin is None:
            return
        for node in graph:
            if hf_plugin.should_pull(node.config, rebuilding=False):
                source = node.config.source
                if source and not (self.project_root / source).exists():
                    hf_plugin.pull(node.config, artifact_name=node.name)
                    self._log(f"PULLED {node.name} from Hugging Face Hub")

    def _parameter_env(self, node) -> dict[str, str]:
        """Expose artifact and trial parameters as AIMAKE_PARAM_* env vars."""
        merged: dict[str, Any] = {}
        merged.update(node.config.parameters)
        merged.update(self._build_parameters)
        env = {f"AIMAKE_PARAM_{key.upper()}": str(value) for key, value in merged.items()}
        env.update(self._fidelity_env)
        return env

    def _maybe_register_artifact(
        self,
        name: str,
        fingerprint: str,
        *,
        metadata: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        if not self.config.registry.enabled or not self.config.registry.auto_register:
            return
        from aimake.registry.store import ArtifactRegistry

        registry = ArtifactRegistry(self.db)
        registry.register(
            name,
            fingerprint,
            build_id=self._build_id,
            stage=self.config.registry.default_stage,
            metadata=metadata,
            metrics=metrics,
        )
        self._log(f"REGISTERED {name} in artifact registry")

    def _build_metadata(self, node) -> dict[str, Any]:
        """Merge user metadata with captured snapshot for rich diffs."""
        snapshot = capture_snapshot(node.name, node.config, self.project_root)
        return merge_metadata_with_snapshot(node.config.metadata, snapshot)

    def _handle_passive(self, node, fingerprint: str, *, metadata: dict[str, Any] | None = None) -> None:
        """Handle passive artifacts (source-only, no command)."""
        self.cache.store(
            node.name,
            fingerprint,
            artifact_type=node.config.type,
            outputs=[node.config.source] if node.config.source else [],
            metadata=metadata or self._build_metadata(node),
        )

    def _parse_metrics(self, node) -> dict[str, Any]:
        if node.config.metrics and node.config.metrics.file:
            return self.metrics_parser.parse_file(node.config.metrics.file)
        return {}

    def _check_outputs_exist(self, graph: Graph | None = None) -> dict[str, bool]:
        graph = graph or self.graph
        result = {}
        for node in graph:
            if node.config.outputs:
                missing = self.process.validate_outputs(
                    node.config.outputs, self.project_root
                )
                result[node.name] = len(missing) == 0
            else:
                result[node.name] = True
        return result

    def _setup_log(self) -> None:
        from aimake.constants import LOGS_DIR

        logs_dir = self.project_root / ".aimake" / LOGS_DIR
        logs_dir.mkdir(parents=True, exist_ok=True)
        build_num = self._build_id or 0
        self._log_path = logs_dir / f"build-{build_num:03d}.log"
        self._log_lines = [
            f"Build #{build_num} started at {datetime.now(timezone.utc).isoformat()}",
        ]

    def _log(self, message: str) -> None:
        self._log_lines.append(message)
        if self.debug:
            print(f"[debug] {message}")

    def _finalize_log(self) -> None:
        if self._log_path:
            self._log_lines.append(
                f"Build finished at {datetime.now(timezone.utc).isoformat()}"
            )
            self._log_path.write_text("\n".join(self._log_lines), encoding="utf-8")

    def clean(
        self,
        *,
        all_cache: bool = False,
        targets: list[str] | None = None,
    ) -> list[str]:
        """Remove build outputs."""
        removed: list[str] = []
        nodes = self.graph if not targets else self.graph.subgraph_for_targets(targets)

        for node in nodes:
            for output in node.config.outputs:
                path = self.project_root / output
                if path.exists():
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                    removed.append(output)
            self.cache.db.delete_artifact(node.name)

        if all_cache:
            self.cache.clear_all()

        return removed
