"""Shared subprocess helpers for CLI-backed plugins."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class CLIError(RuntimeError):
    """Raised when an external CLI command fails."""

    def __init__(self, command: list[str], returncode: int, stderr: str) -> None:
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"Command failed ({returncode}): {' '.join(command)}\n{stderr}".strip()
        )


def require_cli(name: str, *, extra: str) -> str:
    """Return path to executable or raise with install hint."""
    path = shutil.which(name)
    if not path:
        raise ImportError(
            f"{name} is not installed or not on PATH. Install with: pip install aimake[{extra}]"
        )
    return path


def run_cli(
    command: list[str],
    *,
    cwd: Path,
    check: bool = True,
    capture_output: bool = True,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a CLI command in the project root."""
    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=capture_output,
        text=True,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise CLIError(command, result.returncode, result.stderr or result.stdout or "")
    return result
