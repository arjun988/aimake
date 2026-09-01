"""Subprocess execution for artifact commands."""

from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from aimake.models import ExecutionRecord


class ExecutionError(Exception):
    """Raised when a command fails."""

    def __init__(
        self,
        artifact: str,
        command: str,
        exit_code: int,
        stderr: str,
    ) -> None:
        self.artifact = artifact
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(
            f"Build failed for '{artifact}': command exited with code {exit_code}"
        )


class ProcessRunner:
    """Execute shell commands as subprocesses."""

    def __init__(
        self,
        project_root: Path,
        *,
        timeout: float | None = None,
        debug: bool = False,
    ) -> None:
        self.project_root = project_root
        self.timeout = timeout
        self.debug = debug

    def run(
        self,
        artifact: str,
        command: str,
        env_vars: list[str] | None = None,
    ) -> ExecutionRecord:
        """Run a command and return execution record."""
        start = datetime.now(timezone.utc)
        start_mono = time.monotonic()

        env = os.environ.copy()
        if env_vars:
            # Ensure declared env vars are present (already in os.environ)
            if self.debug:
                for var in env_vars:
                    val = env.get(var, "<unset>")
                    if any(s in var.upper() for s in ("KEY", "SECRET", "TOKEN", "PASSWORD")):
                        val = "***REDACTED***"
                    print(f"[debug] env {var}={val}")

        if self.debug:
            print(f"[debug] executing: {command}")
            print(f"[debug] cwd: {self.project_root}")

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.project_root),
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as e:
            end = datetime.now(timezone.utc)
            duration = time.monotonic() - start_mono
            raise ExecutionError(
                artifact, command, -1, f"Command timed out after {self.timeout}s"
            ) from e

        end = datetime.now(timezone.utc)
        duration = time.monotonic() - start_mono

        record = ExecutionRecord(
            artifact=artifact,
            command=command,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            start_time=start,
            end_time=end,
            duration=duration,
        )

        if result.returncode != 0:
            raise ExecutionError(
                artifact, command, result.returncode, result.stderr
            )

        return record

    @staticmethod
    def validate_outputs(
        outputs: list[str],
        project_root: Path,
    ) -> list[str]:
        """Validate that declared outputs exist. Returns list of missing paths."""
        missing = []
        for output in outputs:
            path = project_root / output
            if not path.exists():
                missing.append(output)
        return missing
