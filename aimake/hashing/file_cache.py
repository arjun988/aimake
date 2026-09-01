"""Persistent file hash cache backed by SQLite."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aimake.hashing.files import hash_file, hash_string
from aimake.state.database import StateDatabase

SNAPSHOT_KEY = "_aimake_snapshot"


@dataclass(frozen=True)
class _MemoryEntry:
    hash: str
    size: int
    mtime: float


class FileHashCache:
    """Cache file content hashes keyed by path, size, and mtime."""

    def __init__(self, db: StateDatabase | None) -> None:
        self._db = db
        self._memory: dict[str, _MemoryEntry] = {}

    def hash_file(self, path: Path) -> str:
        """Return SHA-256 hash, reusing cache when size/mtime are unchanged."""
        if not path.is_file():
            return hash_string("missing")

        resolved = path.resolve()
        key = str(resolved)

        stat = path.stat()
        size = stat.st_size
        mtime = stat.st_mtime

        cached = self._memory.get(key)
        if cached is not None and cached.size == size and cached.mtime == mtime:
            return cached.hash

        if self._db is not None:
            row = self._db.conn.execute(
                "SELECT hash, size, mtime FROM file_hashes WHERE path = ?", (key,)
            ).fetchone()
            if row and row["size"] == size and row["mtime"] == mtime:
                entry = _MemoryEntry(row["hash"], size, mtime)
                self._memory[key] = entry
                return row["hash"]

        digest = hash_file(path)
        self._memory[key] = _MemoryEntry(digest, size, mtime)

        if self._db is not None:
            self._db.save_file_hash(key, digest, size, mtime)

        return digest

    def invalidate(self, path: Path) -> None:
        """Remove a path from the cache (e.g. after external edit)."""
        key = str(path.resolve())
        self._memory.pop(key, None)
        if self._db is not None:
            self._db.conn.execute("DELETE FROM file_hashes WHERE path = ?", (key,))
            self._db.conn.commit()
