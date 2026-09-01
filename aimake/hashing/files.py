"""File hashing utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path

from aimake.constants import HASH_PREFIX

CHUNK_SIZE = 65536


def hash_bytes(data: bytes) -> str:
    """Compute SHA-256 hash of bytes, prefixed."""
    digest = hashlib.sha256(data).hexdigest()
    return f"{HASH_PREFIX}{digest}"


def hash_string(text: str) -> str:
    """Compute SHA-256 hash of a string."""
    return hash_bytes(text.encode("utf-8"))


def hash_file(path: Path) -> str:
    """Compute SHA-256 hash of a file's contents."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hasher.update(chunk)
    return f"{HASH_PREFIX}{hasher.hexdigest()}"


def hash_files(paths: list[Path], root: Path | None = None) -> str:
    """Hash multiple files deterministically (sorted by path)."""
    hasher = hashlib.sha256()
    for path in sorted(paths):
        rel = str(path.relative_to(root)) if root else str(path)
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        if path.is_file():
            with open(path, "rb") as f:
                while chunk := f.read(CHUNK_SIZE):
                    hasher.update(chunk)
        hasher.update(b"\0")
    return f"{HASH_PREFIX}{hasher.hexdigest()}"


def strip_prefix(fingerprint: str) -> str:
    """Remove sha256: prefix from fingerprint."""
    if fingerprint.startswith(HASH_PREFIX):
        return fingerprint[len(HASH_PREFIX):]
    return fingerprint
