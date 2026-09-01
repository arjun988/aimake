"""Tests for persistent file hash cache."""

import time
from pathlib import Path
from unittest.mock import patch

from aimake.hashing.file_cache import FileHashCache
from aimake.hashing.files import hash_file
from aimake.state.database import StateDatabase


def test_file_hash_cache_miss_then_hit(tmp_path: Path) -> None:
    db = StateDatabase(tmp_path / ".aimake")
    cache = FileHashCache(db)

    f = tmp_path / "data.txt"
    f.write_text("hello")

    h1 = cache.hash_file(f)
    h2 = cache.hash_file(f)
    assert h1 == h2
    assert h1 == hash_file(f)
    db.close()


def test_file_hash_cache_invalidates_on_content_change(tmp_path: Path) -> None:
    db = StateDatabase(tmp_path / ".aimake")
    cache = FileHashCache(db)

    f = tmp_path / "data.txt"
    f.write_text("version1")
    h1 = cache.hash_file(f)

    f.write_text("version2")
    h2 = cache.hash_file(f)
    assert h1 != h2
    db.close()


def test_file_hash_cache_uses_db_after_mtime_unchanged(tmp_path: Path) -> None:
    db = StateDatabase(tmp_path / ".aimake")
    cache1 = FileHashCache(db)

    f = tmp_path / "data.txt"
    f.write_text("stable content")
    h1 = cache1.hash_file(f)

    # New in-memory cache instance, same DB — should hit DB without re-reading
    cache2 = FileHashCache(db)
    with patch("aimake.hashing.file_cache.hash_file") as mock_hash:
        h2 = cache2.hash_file(f)
        mock_hash.assert_not_called()
    assert h1 == h2
    db.close()


def test_file_hash_cache_invalidates_on_mtime_only_change(tmp_path: Path) -> None:
    """Content unchanged but mtime changed should still return same hash after re-read."""
    db = StateDatabase(tmp_path / ".aimake")
    cache = FileHashCache(db)

    f = tmp_path / "data.txt"
    f.write_text("same content")
    h1 = cache.hash_file(f)

    time.sleep(0.05)
    f.touch()
    h2 = cache.hash_file(f)
    assert h1 == h2  # content same, hash same (mtime changed triggers re-hash)
    db.close()
