"""Test cache system."""

from pathlib import Path

from aimake.cache.store import Cache
from aimake.models import ArtifactStatus


def test_cache_store_and_retrieve(tmp_path: Path) -> None:
    aimake_dir = tmp_path / ".aimake"
    output = tmp_path / "build" / "out.txt"
    output.parent.mkdir(parents=True)
    output.write_text("result")

    cache = Cache(aimake_dir, tmp_path)
    fp = "sha256:abc123"

    cache.store(
        "test",
        fp,
        artifact_type="generic",
        command="echo test",
        outputs=["build/out.txt"],
        duration=1.0,
    )

    assert cache.is_cache_hit("test", fp)
    state = cache.get_artifact_state("test")
    assert state is not None
    assert state.fingerprint == fp
    assert state.status == ArtifactStatus.SUCCESS

    cache.close()


def test_cache_restore(tmp_path: Path) -> None:
    aimake_dir = tmp_path / ".aimake"
    output = tmp_path / "build" / "out.txt"
    output.parent.mkdir(parents=True)
    output.write_text("cached content")

    cache = Cache(aimake_dir, tmp_path)
    fp = "sha256:def456"

    cache.store("artifact", fp, outputs=["build/out.txt"])

    # Remove output and restore
    output.unlink()
    assert not output.exists()

    restored = cache.restore("artifact", fp, ["build/out.txt"])
    assert restored
    assert output.exists()
    assert output.read_text() == "cached content"

    cache.close()


def test_cache_clear(tmp_path: Path) -> None:
    aimake_dir = tmp_path / ".aimake"
    cache = Cache(aimake_dir, tmp_path)
    cache.store("a", "sha256:111", outputs=[])
    cache.clear_all()
    assert cache.get_stored_fingerprints() == {}
    cache.close()
