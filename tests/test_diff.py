"""Tests for diff engine."""

from pathlib import Path

from aimake.config.schema import ArtifactConfig
from aimake.diff.engine import DiffEngine


def test_diff_prompt_unchanged(tmp_path: Path) -> None:
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "system.txt").write_text("Hello world")
    config = ArtifactConfig(type="prompt", source="prompts/system.txt")
    engine = DiffEngine(tmp_path)
    fp = "sha256:abc"
    result = engine.diff_artifact("prompt", config, current_fingerprint=fp, baseline_fingerprint=fp)
    assert not result.has_changes


def test_diff_prompt_changed(tmp_path: Path) -> None:
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "system.txt").write_text("New content")
    config = ArtifactConfig(type="prompt", source="prompts/system.txt")
    engine = DiffEngine(tmp_path)
    result = engine.diff_artifact(
        "prompt", config,
        current_fingerprint="sha256:new",
        baseline_fingerprint="sha256:old",
    )
    assert result.has_changes
    assert result.artifact_type == "prompt"


def test_diff_dataset_stats(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "train.jsonl").write_text('{"text": "a"}\n{"text": "b"}\n')
    config = ArtifactConfig(type="dataset", source="data/train.jsonl")
    engine = DiffEngine(tmp_path)
    result = engine.diff_artifact(
        "dataset", config,
        current_fingerprint="sha256:a",
        baseline_fingerprint="sha256:b",
    )
    assert result.has_changes
    assert any(c.field == "stats" for c in result.changes)


def test_diff_model_parameters(tmp_path: Path) -> None:
    config = ArtifactConfig(
        type="model",
        source="model.json",
        parameters={"temperature": 0.7, "max_tokens": 1024},
    )
    engine = DiffEngine(tmp_path)
    result = engine.diff_artifact(
        "model", config,
        current_fingerprint="sha256:x",
        baseline_fingerprint="sha256:y",
    )
    assert result.has_changes
    assert any(c.field == "parameters" for c in result.changes)
