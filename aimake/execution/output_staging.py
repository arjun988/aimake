"""Atomic artifact output writes via staging and promotion."""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any


class OutputStaging:
    """Stage command outputs, promote atomically on success, discard on failure."""

    def __init__(
        self,
        project_root: Path,
        artifact_name: str,
        outputs: list[str],
        *,
        enabled: bool = True,
    ) -> None:
        self.project_root = project_root
        self.artifact_name = artifact_name
        self.outputs = outputs
        self.enabled = enabled and bool(outputs)
        self._token = uuid.uuid4().hex[:10]
        self._staging_root = project_root / ".aimake" / "staging" / f"{artifact_name}-{self._token}"
        self._backup_root = project_root / ".aimake" / "staging" / f".backup-{artifact_name}-{self._token}"
        self._backup_map: dict[str, Path] = {}
        self._active = False

    def staging_env(self) -> dict[str, str]:
        """Environment variables for staged output paths."""
        if not self.enabled:
            return {}
        mapping = {out: str(self._staging_root / out) for out in self.outputs}
        return {
            "AIMAKE_STAGING_DIR": str(self._staging_root.resolve()),
            "AIMAKE_OUTPUT_PATHS": json.dumps(mapping),
            "AIMAKE_ATOMIC_OUTPUTS": "1",
        }

    def prepare(self) -> None:
        """Create staging dir and backup existing outputs."""
        if not self.enabled:
            return
        self._staging_root.mkdir(parents=True, exist_ok=True)
        self._backup_root.mkdir(parents=True, exist_ok=True)
        self._active = True

        for rel in self.outputs:
            final = self.project_root / rel
            if not final.exists():
                continue
            backup = self._backup_root / rel.replace("/", os.sep).replace("\\", os.sep)
            backup.parent.mkdir(parents=True, exist_ok=True)
            if final.is_dir():
                shutil.copytree(final, backup, dirs_exist_ok=True)
                shutil.rmtree(final, ignore_errors=True)
            else:
                shutil.copy2(final, backup)
                final.unlink(missing_ok=True)
            self._backup_map[rel] = backup

    def promote(self) -> None:
        """Atomically move staged outputs to declared final paths."""
        if not self.enabled or not self._active:
            return

        for rel in self.outputs:
            final = self.project_root / rel
            staged = self._staging_root / rel

            if staged.exists():
                self._atomic_replace(staged, final)
            elif not final.exists():
                raise FileNotFoundError(
                    f"Expected output '{rel}' in staging or project root after build"
                )

        self._remove_tree(self._staging_root)

    def discard_partial(self) -> None:
        """Remove partial outputs after a failed build."""
        for rel in self.outputs:
            final = self.project_root / rel
            staged = self._staging_root / rel
            if staged.exists():
                if staged.is_dir():
                    shutil.rmtree(staged, ignore_errors=True)
                else:
                    staged.unlink(missing_ok=True)
            if final.exists():
                if final.is_dir():
                    shutil.rmtree(final, ignore_errors=True)
                else:
                    final.unlink(missing_ok=True)

    def restore_backup(self) -> None:
        """Restore backed-up outputs after failure."""
        for rel, backup in self._backup_map.items():
            final = self.project_root / rel
            if backup.is_dir():
                if final.exists():
                    shutil.rmtree(final, ignore_errors=True)
                shutil.copytree(backup, final, dirs_exist_ok=True)
            else:
                final.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, final)

    def cleanup(self) -> None:
        """Remove staging and backup directories."""
        self._remove_tree(self._staging_root)
        self._remove_tree(self._backup_root)
        self._active = False

    def _atomic_replace(self, src: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest, ignore_errors=True)
            else:
                dest.unlink(missing_ok=True)
            if sys.platform == "win32":
                for _ in range(10):
                    if not dest.exists():
                        break
                    time.sleep(0.05)

        if src.is_dir():
            if sys.platform == "win32":
                shutil.move(str(src), str(dest))
            else:
                src.rename(dest)
        else:
            if sys.platform == "win32":
                shutil.move(str(src), str(dest))
            else:
                os.replace(src, dest)

    @staticmethod
    def _remove_tree(path: Path) -> None:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
