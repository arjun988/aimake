"""Parallel build scheduler respecting DAG dependencies."""

from __future__ import annotations

import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass, field
from typing import Callable

from aimake.graph.dag import Graph
from aimake.models import BuildAction, BuildPlan


@dataclass
class ScheduleResult:
    """Result of scheduling an artifact."""

    name: str
    success: bool
    error: str | None = None


class BuildScheduler:
    """Schedule artifact builds with parallelism respecting dependencies."""

    def __init__(self, graph: Graph, jobs: int = 0) -> None:
        self.graph = graph
        self.jobs = jobs if jobs > 0 else (os.cpu_count() or 4)

    def execute(
        self,
        plan: BuildPlan,
        runner: Callable[[str], ScheduleResult],
        *,
        on_start: Callable[[str], None] | None = None,
        on_complete: Callable[[ScheduleResult], None] | None = None,
    ) -> list[ScheduleResult]:
        """Execute build plan respecting dependency order with parallelism."""
        to_execute = {
            e.name for e in plan.entries
            if e.action in (BuildAction.RUN, BuildAction.RESTORE)
        }

        if not to_execute:
            return []

        # Track completion
        completed: set[str] = set()
        failed: set[str] = set()
        results: list[ScheduleResult] = []
        lock = threading.Lock()

        # Build dependency map for items to execute
        pending = set(to_execute)
        in_flight: dict[str, Future[ScheduleResult]] = {}

        def can_run(name: str) -> bool:
            if name not in pending:
                return False
            node = self.graph.get(name)
            for dep in node.dependencies:
                if dep in to_execute and dep not in completed:
                    return False
                if dep in failed:
                    return False
            return True

        def submit(executor: ThreadPoolExecutor, name: str) -> None:
            if on_start:
                on_start(name)
            future = executor.submit(runner, name)
            in_flight[name] = future

        with ThreadPoolExecutor(max_workers=self.jobs) as executor:
            while pending or in_flight:
                # Submit ready tasks
                ready = sorted(name for name in pending if can_run(name))
                for name in ready:
                    if len(in_flight) >= self.jobs:
                        break
                    pending.remove(name)
                    submit(executor, name)

                if not in_flight:
                    break

                # Wait for at least one to complete
                done, _ = wait(in_flight.values(), return_when=FIRST_COMPLETED)

                for future in done:
                    # Find which name completed
                    completed_name = None
                    for name, f in in_flight.items():
                        if f is future:
                            completed_name = name
                            break

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
                            # Mark downstream as skipped due to failure
                            self._mark_downstream_failed(
                                completed_name, to_execute, failed
                            )

                    if on_complete:
                        on_complete(result)

                    # Stop if failure and don't continue downstream
                    if not result.success:
                        # Cancel pending downstream
                        for name in list(pending):
                            if self._depends_on_failed(name, failed):
                                pending.discard(name)

        return results

    def _depends_on_failed(self, name: str, failed: set[str]) -> bool:
        """Check if artifact depends on a failed artifact."""
        for dep in self.graph.ancestors(name):
            if dep in failed:
                return True
        return False

    def _mark_downstream_failed(
        self, name: str, to_execute: set[str], failed: set[str]
    ) -> None:
        """Mark all downstream artifacts that depend on failed node."""
        for dep_name in self.graph.descendants(name):
            if dep_name in to_execute:
                failed.add(dep_name)
