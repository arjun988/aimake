"""Parallel build scheduler with GPU and worker awareness."""

from __future__ import annotations

import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass
from typing import Callable

from aimake.graph.dag import Graph
from aimake.models import BuildAction, BuildPlan
from aimake.scheduling.resources import ResourcePool
from aimake.scheduling.workers import WorkerPool


@dataclass
class ScheduleResult:
    """Result of scheduling an artifact."""

    name: str
    success: bool
    error: str | None = None
    worker: str | None = None
    gpus: list[int] | None = None


class BuildScheduler:
    """Schedule artifact builds with parallelism, GPU, and worker constraints."""

    def __init__(
        self,
        graph: Graph,
        jobs: int = 0,
        *,
        resource_pool: ResourcePool | None = None,
        worker_pool: WorkerPool | None = None,
    ) -> None:
        self.graph = graph
        self.jobs = jobs if jobs > 0 else (os.cpu_count() or 4)
        self.resource_pool = resource_pool
        self.worker_pool = worker_pool

    def execute(
        self,
        plan: BuildPlan,
        runner: Callable[[str], ScheduleResult],
        *,
        on_start: Callable[[str], None] | None = None,
        on_complete: Callable[[ScheduleResult], None] | None = None,
    ) -> list[ScheduleResult]:
        to_execute = {
            e.name for e in plan.entries
            if e.action in (BuildAction.RUN, BuildAction.RESTORE)
        }
        if not to_execute:
            return []

        completed: set[str] = set()
        failed: set[str] = set()
        results: list[ScheduleResult] = []
        lock = threading.Lock()
        pending = set(to_execute)
        in_flight: dict[str, Future[ScheduleResult]] = {}

        def gpu_required(name: str) -> int:
            node = self.graph.get(name)
            return node.config.resources.gpu

        def can_run(name: str) -> bool:
            if name not in pending:
                return False
            node = self.graph.get(name)
            for dep in node.dependencies:
                if dep in to_execute and dep not in completed:
                    return False
                if dep in failed:
                    return False
            needed = gpu_required(name)
            if needed > 0 and self.resource_pool:
                if self.resource_pool.available_gpus < needed:
                    return False
            if node.config.worker and self.worker_pool and self.worker_pool.enabled:
                if not self.worker_pool.select_worker(
                    worker_name=node.config.worker,
                    gpu_required=needed,
                ):
                    return False
            elif needed > 0 and self.worker_pool and self.worker_pool.enabled:
                if not self.worker_pool.select_worker(gpu_required=needed):
                    return False
            return True

        def submit(executor: ThreadPoolExecutor, name: str) -> None:
            if on_start:
                on_start(name)
            in_flight[name] = executor.submit(runner, name)

        with ThreadPoolExecutor(max_workers=self.jobs) as executor:
            while pending or in_flight:
                ready = sorted(name for name in pending if can_run(name))
                for name in ready:
                    if len(in_flight) >= self.jobs:
                        break
                    pending.remove(name)
                    submit(executor, name)

                if not in_flight:
                    break

                done, _ = wait(in_flight.values(), return_when=FIRST_COMPLETED)
                for future in done:
                    completed_name = next(
                        (n for n, f in in_flight.items() if f is future), None
                    )
                    if completed_name is None:
                        continue
                    del in_flight[completed_name]
                    try:
                        result = future.result()
                    except Exception as e:
                        result = ScheduleResult(
                            name=completed_name, success=False, error=str(e)
                        )
                    with lock:
                        results.append(result)
                        if result.success:
                            completed.add(completed_name)
                        else:
                            failed.add(completed_name)
                            self._mark_downstream_failed(completed_name, to_execute, failed)
                    if on_complete:
                        on_complete(result)
                    if not result.success:
                        for name in list(pending):
                            if self._depends_on_failed(name, failed):
                                pending.discard(name)
        return results

    def _depends_on_failed(self, name: str, failed: set[str]) -> bool:
        return any(dep in failed for dep in self.graph.ancestors(name))

    def _mark_downstream_failed(
        self, name: str, to_execute: set[str], failed: set[str]
    ) -> None:
        for dep_name in self.graph.descendants(name):
            if dep_name in to_execute:
                failed.add(dep_name)
