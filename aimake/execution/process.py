"""Subprocess and remote execution for artifact commands."""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aimake.config.schema import WorkerConfig
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
    """Execute shell commands locally or on remote workers."""

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
        *,
        extra_env: dict[str, str] | None = None,
        worker: WorkerConfig | None = None,
    ) -> ExecutionRecord:
        """Run a command locally or on a remote worker."""
        if worker:
            return self._run_remote(artifact, command, worker, env_vars, extra_env)
        return self._run_local(artifact, command, env_vars, extra_env)

    def _run_local(
        self,
        artifact: str,
        command: str,
        env_vars: list[str] | None,
        extra_env: dict[str, str] | None,
    ) -> ExecutionRecord:
        start = datetime.now(timezone.utc)
        start_mono = time.monotonic()

        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        if env_vars and self.debug:
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
            raise ExecutionError(artifact, command, result.returncode, result.stderr)
        return record

    def _run_remote(
        self,
        artifact: str,
        command: str,
        worker: WorkerConfig,
        env_vars: list[str] | None,
        extra_env: dict[str, str] | None,
    ) -> ExecutionRecord:
        start = datetime.now(timezone.utc)
        start_mono = time.monotonic()

        target = f"{worker.user}@{worker.host}" if worker.user else worker.host
        workdir = worker.workdir or str(self.project_root)

        env_exports = ""
        if extra_env:
            parts = [f"export {k}={shlex.quote(v)}" for k, v in extra_env.items()]
            env_exports = " && ".join(parts) + " && "

        remote_cmd = f"cd {shlex.quote(workdir)} && {env_exports}{command}"
        ssh_cmd = ["ssh", *worker.ssh_options, target, remote_cmd]

        if self.debug:
            print(f"[debug] remote worker: {worker.name} ({target})")
            print(f"[debug] ssh command: {' '.join(ssh_cmd)}")

        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise ExecutionError(
                artifact, command, -1, f"Remote command timed out after {self.timeout}s"
            ) from e

        end = datetime.now(timezone.utc)
        duration = time.monotonic() - start_mono
        record = ExecutionRecord(
            artifact=artifact,
            command=f"[{worker.name}] {command}",
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            start_time=start,
            end_time=end,
            duration=duration,
        )
        if result.returncode != 0:
            raise ExecutionError(
                artifact, record.command, result.returncode, result.stderr
            )
        return record

    @staticmethod
    def validate_outputs(outputs: list[str], project_root: Path) -> list[str]:
        missing = []
        for output in outputs:
            path = project_root / output
            if not path.exists():
                missing.append(output)
        return missing
