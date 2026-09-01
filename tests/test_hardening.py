"""Hardening tests: force rebuild, targeted builds, corrupted cache."""

from pathlib import Path

from aimake.cache.store import Cache
from aimake.config.schema import AimakeConfig, ArtifactConfig, ProjectConfig
from aimake.execution.runner import BuildRunner
from aimake.graph.dag import Graph
from aimake.models import ArtifactStatus


def _chain_config() -> AimakeConfig:
    return AimakeConfig(
        project=ProjectConfig(name="test"),
        artifacts={
            "a": ArtifactConfig(
                type="generic",
                command='python -c "import os; os.makedirs(\'build/a\', exist_ok=True); open(\'build/a/o.txt\',\'w\').write(\'a\')"',
                outputs=["build/a/o.txt"],
            ),
            "b": ArtifactConfig(
                type="generic",
                depends_on=["a"],
                command='python -c "import os; os.makedirs(\'build/b\', exist_ok=True); open(\'build/b/o.txt\',\'w\').write(\'b\')"',
                outputs=["build/b/o.txt"],
            ),
            "c": ArtifactConfig(
                type="generic",
                depends_on=["b"],
                command='python -c "import os; os.makedirs(\'build/c\', exist_ok=True); open(\'build/c/o.txt\',\'w\').write(\'c\')"',
                outputs=["build/c/o.txt"],
            ),
        },
    )


def test_force_rebuild_single_target(tmp_path: Path) -> None:
    config = _chain_config()
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path, config)

    runner = BuildRunner(tmp_path, config, graph, cache)
    runner.build()
    r2 = BuildRunner(tmp_path, config, graph, cache)
    result = r2.build(force={"b"})
    assert result.success
    assert "b" in result.rebuilt
    assert "c" in result.rebuilt  # downstream of forced b
    assert "a" not in result.rebuilt
    cache.close()


def test_targeted_build_subset(tmp_path: Path) -> None:
    config = _chain_config()
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path, config)

    runner = BuildRunner(tmp_path, config, graph, cache)
    runner.build()

    runner2 = BuildRunner(tmp_path, config, graph, cache)
    runner2.build(targets=["b"])
    plan = runner2.plan(targets=["b"])
    names = {e.name for e in plan.entries}
    assert names == {"a", "b"}
    assert "c" not in names
    cache.close()


def test_corrupted_cache_detected(tmp_path: Path) -> None:
    config = AimakeConfig(
        project=ProjectConfig(name="test"),
        artifacts={
            "x": ArtifactConfig(type="dataset", source="x.txt"),
        },
    )
    (tmp_path / "x.txt").write_text("data")

    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path, config)
    runner = BuildRunner(tmp_path, config, graph, cache)
    runner.build()

    # Corrupt cache entry by removing metadata
    for fp in cache.fs.list_entries():
        entry = cache.fs._entry_dir(f"sha256:{fp}")
        meta = entry / "metadata.json"
        if meta.exists():
            meta.unlink()

    corrupted = cache.verify_integrity()
    assert len(corrupted) >= 1
    cache.close()


def test_missing_output_marks_stale(tmp_path: Path) -> None:
    config = AimakeConfig(
        project=ProjectConfig(name="test"),
        artifacts={
            "a": ArtifactConfig(
                type="generic",
                command='python -c "import os; os.makedirs(\'build/a\', exist_ok=True); open(\'build/a/o.txt\',\'w\').write(\'a\')"',
                outputs=["build/a/o.txt"],
            ),
        },
    )
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path, config)
    runner = BuildRunner(tmp_path, config, graph, cache)
    runner.build()

    # Delete output but fingerprint still in DB
    import shutil
    shutil.rmtree(tmp_path / "build")

    runner2 = BuildRunner(tmp_path, config, graph, cache)
    statuses = runner2.compute_statuses()
    assert statuses["a"] in (ArtifactStatus.STALE, ArtifactStatus.CHANGED)
    cache.close()


def test_diff_cli_integration_via_project(tmp_path: Path) -> None:
    from aimake.diff.snapshots import extract_snapshot
    from aimake.project import Project

    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "p.txt").write_text("v1")
    (tmp_path / "aimake.yaml").write_text("""
project:
  name: t
artifacts:
  prompt:
    type: prompt
    source: prompts/p.txt
""")
    project = Project.load(tmp_path / "aimake.yaml")
    project.build()
    (tmp_path / "prompts" / "p.txt").write_text("v2 changed")
    result = project.diff("prompt")
    assert result.has_changes
    project.close()
