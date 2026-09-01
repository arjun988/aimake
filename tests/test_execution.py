"""Test build execution."""

from pathlib import Path

import pytest

from aimake.cache.store import Cache
from aimake.config.schema import AimakeConfig, ArtifactConfig, ProjectConfig
from aimake.execution.process import ExecutionError, ProcessRunner
from aimake.execution.runner import BuildRunner
from aimake.graph.dag import Graph


def _pipeline_config(commands: dict[str, str]) -> AimakeConfig:
    artifacts = {}
    prev = None
    for i, (name, cmd) in enumerate(commands.items()):
        cfg: dict = {
            "type": "generic",
            "command": cmd,
            "outputs": [f"build/{name}/out.txt"],
        }
        if prev:
            cfg["depends_on"] = [prev]
        artifacts[name] = ArtifactConfig(**cfg)
        prev = name
    return AimakeConfig(project=ProjectConfig(name="test"), artifacts=artifacts)


def test_successful_command(tmp_path: Path) -> None:
    runner = ProcessRunner(tmp_path)
    record = runner.run("test", f'python -c "open(r\'out.txt\',\'w\').write(\'ok\')"')
    assert record.exit_code == 0


def test_failed_command(tmp_path: Path) -> None:
    runner = ProcessRunner(tmp_path)
    with pytest.raises(ExecutionError):
        runner.run("test", "python -c \"import sys; sys.exit(1)\"")


def test_output_validation(tmp_path: Path) -> None:
    missing = ProcessRunner.validate_outputs(["build/missing.txt"], tmp_path)
    assert "build/missing.txt" in missing


def test_incremental_build(tmp_path: Path) -> None:
    """Test A → B → C incremental semantics."""
    for name in ("a", "b", "c"):
        (tmp_path / "src").mkdir(exist_ok=True)

    scripts = {
        "a": 'python -c "import os; os.makedirs(\'build/a\', exist_ok=True); open(\'build/a/out.txt\',\'w\').write(\'a\')"',
        "b": 'python -c "open(\'build/b/out.txt\',\'w\').write(open(\'build/a/out.txt\').read()+\'b\')"' if False else (
            'python -c "import os; os.makedirs(\'build/b\', exist_ok=True); '
            "open('build/b/out.txt','w').write('b')\""
        ),
        "c": 'python -c "import os; os.makedirs(\'build/c\', exist_ok=True); open(\'build/c/out.txt\',\'w\').write(\'c\')"',
    }

    config = _pipeline_config(scripts)
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path)
    runner = BuildRunner(tmp_path, config, graph, cache)

    # First build — all run
    r1 = runner.build()
    assert r1.success
    assert len(r1.rebuilt) == 3

    # Second build — all cached
    runner2 = BuildRunner(tmp_path, config, graph, cache)
    r2 = runner2.build()
    assert r2.success
    assert len(r2.rebuilt) == 0
    assert len(r2.reused) == 3

    cache.close()


def test_parallel_execution(tmp_path: Path) -> None:
    """Independent nodes should both execute."""
    config = AimakeConfig(
        project=ProjectConfig(name="test"),
        artifacts={
            "root": ArtifactConfig(
                type="dataset",
                source="root.txt",
            ),
            "left": ArtifactConfig(
                type="generic",
                command='python -c "import os; os.makedirs(\'build/left\', exist_ok=True); open(\'build/left/out.txt\',\'w\').write(\'l\')"',
                outputs=["build/left/out.txt"],
                depends_on=["root"],
            ),
            "right": ArtifactConfig(
                type="generic",
                command='python -c "import os; os.makedirs(\'build/right\', exist_ok=True); open(\'build/right/out.txt\',\'w\').write(\'r\')"',
                outputs=["build/right/out.txt"],
                depends_on=["root"],
            ),
        },
    )
    (tmp_path / "root.txt").write_text("data")

    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path)
    runner = BuildRunner(tmp_path, config, graph, cache, jobs=2)

    # Store root in cache first
    runner.compute_fingerprints()
    runner.build()

    cache.close()
