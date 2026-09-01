"""Git integration for build metadata."""

from __future__ import annotations

import subprocess
from pathlib import Path

from aimake.models import GitInfo


def _run_git(args: list[str], cwd: Path) -> str | None:
    """Run a git command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


def is_git_repo(path: Path) -> bool:
    """Check if path is inside a git repository."""
    return _run_git(["rev-parse", "--git-dir"], path) is not None


def get_git_info(project_root: Path) -> GitInfo:
    """Collect git metadata if available."""
    if not is_git_repo(project_root):
        return GitInfo(available=False)

    commit = _run_git(["rev-parse", "HEAD"], project_root)
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], project_root)
    status = _run_git(["status", "--porcelain"], project_root)
    dirty = bool(status) if status is not None else None

    return GitInfo(
        commit=commit,
        branch=branch,
        dirty=dirty,
        available=commit is not None,
    )
