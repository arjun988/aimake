"""Cache backend protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CacheBackend(Protocol):
    """Protocol for content-addressable cache storage backends."""

    def has(self, fingerprint: str) -> bool:
        """Return True if the fingerprint exists in this backend."""

    def get(self, fingerprint: str) -> dict[str, Any] | None:
        """Load cache entry metadata."""

    def store(
        self,
        fingerprint: str,
        artifact_name: str,
        outputs: list[str],
        project_root: Path,
        *,
        command: str | None = None,
        duration: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store artifact outputs."""

    def restore(self, fingerprint: str, outputs: list[str], project_root: Path) -> bool:
        """Restore cached outputs to the project."""

    def remove(self, fingerprint: str) -> None:
        """Remove a cache entry."""

    def clear(self) -> None:
        """Remove all cache entries."""

    def verify(self, fingerprint: str) -> bool:
        """Verify cache entry integrity."""

    def list_entries(self) -> list[str]:
        """List all cache entry fingerprints (hash only, no prefix)."""
