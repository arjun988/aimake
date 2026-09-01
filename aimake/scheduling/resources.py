"""GPU detection and resource pool management."""

from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass, field


@dataclass
class GPUInfo:
    """Information about a detected GPU."""

    index: int
    name: str
    memory_mb: int = 0


class GPUDetector:
    """Detect available NVIDIA GPUs."""

    @staticmethod
    def detect() -> list[GPUInfo]:
        gpus = GPUDetector._detect_nvidia_smi()
        if gpus:
            return gpus
        return GPUDetector._detect_cuda_env()

    @staticmethod
    def _detect_nvidia_smi() -> list[GPUInfo]:
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return []
            gpus: list[GPUInfo] = []
            for line in result.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 2:
                    idx = int(parts[0])
                    name = parts[1]
                    mem = int(float(parts[2])) if len(parts) > 2 else 0
                    gpus.append(GPUInfo(index=idx, name=name, memory_mb=mem))
            return gpus
        except (subprocess.SubprocessError, FileNotFoundError, ValueError):
            return []

    @staticmethod
    def _detect_cuda_env() -> list[GPUInfo]:
        visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
        if visible == "-1":
            return []
        if visible and visible != "":
            indices = [int(x) for x in visible.split(",") if x.strip().isdigit()]
            return [GPUInfo(index=i, name="cuda") for i in indices]
        return []


class ResourcePool:
    """Track and allocate GPU resources across parallel builds."""

    def __init__(self, gpu_count: int | None = None) -> None:
        detected = GPUDetector.detect()
        if gpu_count is None or gpu_count == 0:
            self.total_gpus = len(detected) if detected else 0
        else:
            self.total_gpus = gpu_count
        self._available = list(range(self.total_gpus))
        self._lock = threading.Lock()
        self._in_use: dict[int, str] = {}  # gpu_index -> artifact name

    @property
    def available_gpus(self) -> int:
        with self._lock:
            return len(self._available)

    def acquire(self, count: int, artifact: str) -> list[int] | None:
        """Acquire GPU indices. Returns None if not enough GPUs available."""
        if count <= 0:
            return []
        with self._lock:
            if len(self._available) < count:
                return None
            indices = self._available[:count]
            self._available = self._available[count:]
            for idx in indices:
                self._in_use[idx] = artifact
            return indices

    def release(self, indices: list[int]) -> None:
        with self._lock:
            for idx in indices:
                self._in_use.pop(idx, None)
                if idx not in self._available:
                    self._available.append(idx)
            self._available.sort()

    def gpu_env(self, indices: list[int]) -> dict[str, str]:
        if not indices:
            return {}
        return {"CUDA_VISIBLE_DEVICES": ",".join(str(i) for i in indices)}
