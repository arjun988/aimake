"""Filesystem cache for artifact outputs."""

from __future__ import annotations

import json
import shutil
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from aimake.constants import CACHE_DIR
from aimake.hashing.files import strip_prefix


class FilesystemCache:
    """Content-addressable filesystem cache."""

    def __init__(self, aimake_dir: Path) -> None:
        self.cache_dir = aimake_dir / CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cleanup_stale_tmp_dirs()

    def _cleanup_stale_tmp_dirs(self) -> None:
        if not self.cache_dir.exists():
            return
        for item in self.cache_dir.iterdir():
            if item.is_dir() and item.name.startswith(".tmp-"):
                shutil.rmtree(item, ignore_errors=True)

    def _replace_dir(self, src: Path, dest: Path) -> None:
        """Atomically replace dest with src (cross-platform)."""
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
            if sys.platform == "win32":
                for _ in range(10):
                    if not dest.exists():
                        break
                    time.sleep(0.05)

        if sys.platform == "win32":
            shutil.move(str(src), str(dest))
        else:
            src.rename(dest)

    def _entry_dir(self, fingerprint: str) -> Path:
        return self.cache_dir / strip_prefix(fingerprint)

    def has(self, fingerprint: str) -> bool:
        """Check if cache entry exists and is valid."""
        entry = self._entry_dir(fingerprint)
        meta = entry / "metadata.json"
        return entry.is_dir() and meta.is_file()

    def get(self, fingerprint: str) -> dict[str, Any] | None:
        """Load cache entry metadata."""
        entry = self._entry_dir(fingerprint)
        meta_path = entry / "metadata.json"
        if not meta_path.is_file():
            return None
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)

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
        """Store artifact outputs in cache with atomic write."""
        with self._lock:
            entry = self._entry_dir(fingerprint)
            if entry.exists() and self.has(fingerprint):
                return

            tmp = self.cache_dir / f".tmp-{uuid.uuid4().hex[:12]}"

            try:
                tmp.mkdir(parents=True)
                artifacts_dir = tmp / "artifacts"
                artifacts_dir.mkdir()

                stored_outputs: list[str] = []
                for output in outputs:
                    src = project_root / output
                    if src.exists():
                        dest = artifacts_dir / output.replace("/", "_").replace("\\", "_")
                        if src.is_dir():
                            shutil.copytree(src, dest, dirs_exist_ok=True)
                        else:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, dest)
                        stored_outputs.append(output)

                meta = {
                    "fingerprint": fingerprint,
                    "artifact": artifact_name,
                    "outputs": stored_outputs,
                    "command": command,
                    "duration": duration,
                    "metadata": metadata or {},
                }
                with open(tmp / "metadata.json", "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)

                self._replace_dir(tmp, entry)
            except Exception:
                if tmp.exists():
                    shutil.rmtree(tmp, ignore_errors=True)
                raise

    def restore(
        self,
        fingerprint: str,
        outputs: list[str],
        project_root: Path,
    ) -> bool:
        """Restore cached outputs to project build directory."""
        entry = self._entry_dir(fingerprint)
        if not self.has(fingerprint):
            return False

        artifacts_dir = entry / "artifacts"
        meta = self.get(fingerprint)
        if not meta:
            return False

        for output in outputs:
            cache_name = output.replace("/", "_").replace("\\", "_")
            src = artifacts_dir / cache_name
            dest = project_root / output
            if src.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(src, dest)
                else:
                    shutil.copy2(src, dest)
        return True

    def remove(self, fingerprint: str) -> None:
        """Remove a cache entry."""
        entry = self._entry_dir(fingerprint)
        if entry.exists():
            shutil.rmtree(entry)

    def clear(self) -> None:
        """Remove all cache entries."""
        if self.cache_dir.exists():
            for item in self.cache_dir.iterdir():
                if item.is_dir() and not item.name.startswith(".tmp-"):
                    shutil.rmtree(item)

    def verify(self, fingerprint: str) -> bool:
        """Verify cache entry integrity."""
        entry = self._entry_dir(fingerprint)
        if not entry.is_dir():
            return False
        meta_path = entry / "metadata.json"
        if not meta_path.is_file():
            return False
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            artifacts_dir = entry / "artifacts"
            for output in meta.get("outputs", []):
                cache_name = output.replace("/", "_").replace("\\", "_")
                if not (artifacts_dir / cache_name).exists():
                    return False
            return True
        except (json.JSONDecodeError, OSError):
            return False

    def list_entries(self) -> list[str]:
        """List all cache entry fingerprints."""
        if not self.cache_dir.exists():
            return []
        return [
            d.name for d in self.cache_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
