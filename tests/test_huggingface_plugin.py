"""Tests for the Hugging Face plugin."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aimake.config.schema import (
    AimakeConfig,
    ArtifactConfig,
    HuggingFacePluginConfig,
    PluginsConfig,
    ProjectConfig,
)
from aimake.plugins.huggingface import HuggingFacePlugin
from aimake.plugins.loader import load_plugins


def _hf_artifact(**meta) -> ArtifactConfig:
    return ArtifactConfig(
        type="model",
        source="models/test-model",
        metadata={"huggingface": {"repo_id": "org/test-model", **meta}},
    )


def test_load_hf_plugin() -> None:
    config = AimakeConfig(
        project=ProjectConfig(name="t"),
        artifacts={"m": ArtifactConfig(type="prompt", source="p.txt")},
        plugins=PluginsConfig(huggingface=HuggingFacePluginConfig(enabled=True)),
    )
    manager = load_plugins(config, Path("/tmp"))
    assert manager.get("huggingface") is not None


def test_should_pull_when_source_missing(tmp_path: Path) -> None:
    plugin = HuggingFacePlugin(HuggingFacePluginConfig(enabled=True), tmp_path)
    artifact = _hf_artifact()
    assert plugin.should_pull(artifact, rebuilding=False) is True


def test_should_not_pull_when_disabled(tmp_path: Path) -> None:
    plugin = HuggingFacePlugin(
        HuggingFacePluginConfig(enabled=True, auto_pull=False),
        tmp_path,
    )
    artifact = _hf_artifact(pull=False)
    (tmp_path / "models" / "test-model").mkdir(parents=True)
    assert plugin.should_pull(artifact, rebuilding=True) is False


def test_pull_calls_snapshot_download(tmp_path: Path) -> None:
    plugin = HuggingFacePlugin(HuggingFacePluginConfig(enabled=True), tmp_path)
    artifact = _hf_artifact()

    mock_hf = MagicMock()
    mock_snapshot = MagicMock(return_value="/downloaded")
    mock_hf.snapshot_download = mock_snapshot

    with patch.dict("sys.modules", {"huggingface_hub": mock_hf}):
        path = plugin.pull(artifact, artifact_name="m")

    assert path == tmp_path / "models" / "test-model"
    mock_snapshot.assert_called_once()
    call_kwargs = mock_snapshot.call_args.kwargs
    assert call_kwargs["repo_id"] == "org/test-model"
    assert call_kwargs["repo_type"] == "model"


def test_push_calls_upload_folder(tmp_path: Path) -> None:
    plugin = HuggingFacePlugin(HuggingFacePluginConfig(enabled=True), tmp_path)
    out_dir = tmp_path / "models" / "test-model"
    out_dir.mkdir(parents=True)
    (out_dir / "config.json").write_text("{}", encoding="utf-8")
    artifact = _hf_artifact(push=True)

    mock_api = MagicMock()
    mock_hf = MagicMock()
    mock_hf.HfApi.return_value = mock_api

    with patch.dict("sys.modules", {"huggingface_hub": mock_hf}):
        repo = plugin.push(artifact, artifact_name="m")

    assert repo == "org/test-model"
    mock_api.create_repo.assert_called_once()
    mock_api.upload_folder.assert_called_once()


def test_project_hf_pull(tmp_path: Path) -> None:
    from aimake.project import Project

    (tmp_path / "aimake.yaml").write_text(
        """
project:
  name: t
plugins:
  huggingface:
    enabled: true
artifacts:
  model:
    type: model
    source: models/hf-model
    metadata:
      huggingface:
        repo_id: org/demo
""",
        encoding="utf-8",
    )
    project = Project.load(tmp_path / "aimake.yaml")
    plugin = project.plugin_manager.get("huggingface")
    assert plugin is not None

    with patch.object(plugin, "pull", return_value=tmp_path / "models" / "hf-model") as mock_pull:
        path = project.hf_pull("model")
        mock_pull.assert_called_once()
        assert "hf-model" in str(path)
    project.close()


def test_hf_pull_requires_plugin(tmp_path: Path) -> None:
    from aimake.project import Project

    (tmp_path / "aimake.yaml").write_text(
        """
project:
  name: t
artifacts:
  model:
    type: model
    source: models/x
""",
        encoding="utf-8",
    )
    project = Project.load(tmp_path / "aimake.yaml")
    with pytest.raises(ValueError, match="not enabled"):
        project.hf_pull("model")
    project.close()
