"""Directory hashing with glob support."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from aimake.hashing.files import hash_file, hash_files


def expand_glob(pattern: str, root: Path) -> list[Path]:
    """Expand a glob pattern relative to root."""
    pattern = pattern.replace("\\", "/")

    if "**" in pattern:
        base_part = pattern.split("**")[0].rstrip("/")
        if base_part:
            base = root / base_part
        else:
            base = root
        if not base.exists():
            return []
        suffix = pattern.split("**", 1)[1].lstrip("/")
        if suffix:
            glob_pattern = f"**/{suffix}" if not suffix.startswith("*") else suffix
        else:
            glob_pattern = "**/*"
        return sorted(p for p in base.glob(glob_pattern) if p.is_file())

    path = root / pattern
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(p for p in path.rglob("*") if p.is_file())

    # Try glob from root
    matches = sorted(root.glob(pattern))
    return [p for p in matches if p.is_file()]


def hash_directory(path: Path) -> str:
    """Hash all files in a directory deterministically."""
    if not path.exists():
        return hash_files([])
    files = sorted(p for p in path.rglob("*") if p.is_file())
    return hash_files(files, root=path.parent if path.is_dir() else path.parent)


def hash_inputs(inputs: list[str], root: Path) -> str:
    """Hash declared inputs (files, directories, globs)."""
    all_files: list[Path] = []
    for pattern in inputs:
        pattern = pattern.replace("\\", "/")
        if "**" in pattern or "*" in pattern:
            all_files.extend(expand_glob(pattern, root))
        else:
            path = root / pattern
            if path.is_file():
                all_files.append(path)
            elif path.is_dir():
                all_files.extend(sorted(p for p in path.rglob("*") if p.is_file()))
    return hash_files(sorted(set(all_files)), root=root)
