"""Tests for GPU scheduling and worker pool."""

from aimake.config.schema import ArtifactConfig, ResourceConfig, WorkerConfig, WorkersConfig
from aimake.scheduling.resources import ResourcePool
from aimake.scheduling.workers import WorkerPool


def test_resource_pool_acquire_release() -> None:
    pool = ResourcePool(gpu_count=2)
    indices = pool.acquire(1, "test-artifact")
    assert indices is not None
    assert len(indices) == 1
    assert pool.available_gpus == 1
    pool.release(indices)
    assert pool.available_gpus == 2


def test_resource_pool_exhausted() -> None:
    pool = ResourcePool(gpu_count=1)
    a = pool.acquire(1, "a")
    b = pool.acquire(1, "b")
    assert a is not None
    assert b is None
    pool.release(a)  # type: ignore[arg-type]


def test_resource_pool_zero_gpu() -> None:
    pool = ResourcePool(gpu_count=0)
    indices = pool.acquire(0, "cpu-only")
    assert indices == []


def test_worker_pool_selection() -> None:
    config = WorkersConfig(
        enabled=True,
        workers=[
            WorkerConfig(name="gpu1", host="worker1", gpus=2, jobs=2),
            WorkerConfig(name="cpu1", host="worker2", gpus=0, jobs=4),
        ],
    )
    pool = WorkerPool(config)
    w = pool.select_worker(gpu_required=1)
    assert w is not None
    assert w.config.name == "gpu1"


def test_worker_pool_acquire_release() -> None:
    config = WorkersConfig(
        enabled=True,
        workers=[WorkerConfig(name="w1", host="host", gpus=1, jobs=1)],
    )
    pool = WorkerPool(config)
    state = pool.select_worker(gpu_required=1)
    assert state is not None
    assert pool.acquire(state, 1)
    assert not pool.select_worker(gpu_required=1)
    pool.release(state, 1)
    assert pool.select_worker(gpu_required=1) is not None
