"""Tests for rich diffs with stored snapshots."""

from pathlib import Path

from aimake.config.schema import ArtifactConfig
from aimake.diff.engine import DiffEngine
from aimake.diff.snapshots import capture_snapshot


def test_rich_prompt_diff_with_snapshot(tmp_path: Path) -> None:
    (tmp_path / "prompts").mkdir()
    path = tmp_path / "prompts" / "system.txt"
    path.write_text("You are a helpful assistant.\nBe concise.")

    config = ArtifactConfig(type="prompt", source="prompts/system.txt")
    baseline_snapshot = capture_snapshot("prompt", config, tmp_path)

    path.write_text("You are a helpful assistant.\nBe detailed and thorough.")

    engine = DiffEngine(tmp_path)
    result = engine.diff_artifact(
        "prompt",
        config,
        current_fingerprint="sha256:new",
        baseline_fingerprint="sha256:old",
        baseline_snapshot=baseline_snapshot,
    )

    assert result.has_changes
    assert "Be concise" in result.unified_diff or "---" in result.unified_diff
    assert any(c.field == "content" for c in result.changes)


def test_rich_dataset_diff_row_count(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    path = tmp_path / "data" / "train.jsonl"
    path.write_text('{"id": "1"}\n{"id": "2"}\n')

    config = ArtifactConfig(type="dataset", source="data/train.jsonl")
    baseline_snapshot = capture_snapshot("dataset", config, tmp_path)

    path.write_text('{"id": "1"}\n{"id": "2"}\n{"id": "3"}\n')

    engine = DiffEngine(tmp_path)
    result = engine.diff_artifact(
        "dataset",
        config,
        current_fingerprint="sha256:new",
        baseline_fingerprint="sha256:old",
        baseline_snapshot=baseline_snapshot,
    )

    assert result.has_changes
    row_change = next((c for c in result.changes if c.field == "row_count"), None)
    assert row_change is not None
    assert row_change.old_value == 2
    assert row_change.new_value == 3


def test_rich_model_parameter_diff(tmp_path: Path) -> None:
    config = ArtifactConfig(
        type="model",
        source="model.json",
        parameters={"temperature": 0.7, "max_tokens": 1024},
    )
    baseline_snapshot = capture_snapshot("model", config, tmp_path)

    config.parameters = {"temperature": 0.9, "max_tokens": 1024}

    engine = DiffEngine(tmp_path)
    result = engine.diff_artifact(
        "model",
        config,
        current_fingerprint="sha256:new",
        baseline_fingerprint="sha256:old",
        baseline_snapshot=baseline_snapshot,
    )

    assert result.has_changes
    assert "temperature" in result.unified_diff


def test_snapshot_captured_on_build(tmp_path: Path) -> None:
    """Integration: build stores snapshot in artifact metadata."""
    from aimake.cache.store import Cache
    from aimake.config.schema import AimakeConfig, ArtifactConfig, ProjectConfig
    from aimake.diff.snapshots import extract_snapshot
    from aimake.execution.runner import BuildRunner
    from aimake.graph.dag import Graph

    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "system.txt").write_text("Hello")

    config = AimakeConfig(
        project=ProjectConfig(name="test"),
        artifacts={
            "prompt": ArtifactConfig(type="prompt", source="prompts/system.txt"),
        },
    )
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path, config)
    runner = BuildRunner(tmp_path, config, graph, cache)
    result = runner.build()
    assert result.success

    state = cache.get_artifact_state("prompt")
    snap = extract_snapshot(state.metadata if state else None)
    assert snap is not None
    assert snap.get("prompt_text") == "Hello"
    cache.close()
