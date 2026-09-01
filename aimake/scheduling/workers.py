"""Distributed worker pool for remote execution."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from aimake.config.schema import WorkerConfig, WorkersConfig


@dataclass
class WorkerState:
    """Runtime state for a worker."""

    config: WorkerConfig
    active_jobs: int = 0
    gpus_in_use: int = 0


class WorkerPool:
    """Manage remote workers and assign artifacts."""

    def __init__(self, config: WorkersConfig) -> None:
        self.config = config
        self._workers: dict[str, WorkerState] = {
            w.name: WorkerState(config=w) for w in config.workers
        }
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.config.enabled and bool(self._workers)

    def get(self, name: str) -> WorkerState | None:
        return self._workers.get(name)

    def select_worker(
        self,
        *,
        worker_name: str | None = None,
        gpu_required: int = 0,
    ) -> WorkerState | None:
        """Select a worker for an artifact."""
        if not self.enabled:
            return None

        with self._lock:
            if worker_name:
                state = self._workers.get(worker_name)
                if state and self._can_assign(state, gpu_required):
                    return state
                return None

            # Prefer worker with most free GPU capacity
            candidates = sorted(
                self._workers.values(),
                key=lambda w: (
                    -(w.config.gpus - w.gpus_in_use),
                    w.active_jobs,
                ),
            )
            for state in candidates:
                if self._can_assign(state, gpu_required):
                    return state
        return None

    def acquire(self, state: WorkerState, gpu_count: int = 0) -> bool:
        with self._lock:
            if not self._can_assign(state, gpu_count):
                return False
            state.active_jobs += 1
            state.gpus_in_use += gpu_count
            return True

    def release(self, state: WorkerState, gpu_count: int = 0) -> None:
        with self._lock:
            state.active_jobs = max(0, state.active_jobs - 1)
            state.gpus_in_use = max(0, state.gpus_in_use - gpu_count)

    def _can_assign(self, state: WorkerState, gpu_count: int) -> bool:
        if state.active_jobs >= state.config.jobs:
            return False
        if gpu_count > 0 and state.config.gpus > 0:
            return (state.config.gpus - state.gpus_in_use) >= gpu_count
        if gpu_count > 0 and state.config.gpus == 0:
            return False
        return True

    def list_workers(self) -> list[dict]:
        return [
            {
                "name": s.config.name,
                "host": s.config.host,
                "gpus": s.config.gpus,
                "jobs": s.config.jobs,
                "active_jobs": s.active_jobs,
                "gpus_in_use": s.gpus_in_use,
            }
            for s in self._workers.values()
        ]
