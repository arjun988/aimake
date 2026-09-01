"""Tests for W&B, DVC, Docker, and Ollama plugins."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aimake.config.schema import (
    AimakeConfig,
    ArtifactConfig,
    DockerPluginConfig,
    DvcPluginConfig,
    OllamaPluginConfig,
    PluginsConfig,
    ProjectConfig,
    WandbPluginConfig,
)
from aimake.plugins.base import PluginManager
from aimake.plugins.docker_plugin import DockerPlugin
from aimake.plugins.dvc import DvcPlugin
from aimake.plugins.loader import load_plugins
from aimake.plugins.ollama import OllamaPlugin
from aimake.plugins.wandb_plugin import WandbPlugin


def test_load_all_plugins() -> None:
    config = AimakeConfig(
        project=ProjectConfig(name="t"),
        artifacts={"m": ArtifactConfig(type="prompt", source="p.txt")},
        plugins=PluginsConfig(
            huggingface=None,
            wandb=WandbPluginConfig(enabled=True, project="demo"),
            dvc=DvcPluginConfig(enabled=True),
            docker=DockerPluginConfig(enabled=True, default_image="python:3.11"),
            ollama=OllamaPluginConfig(enabled=True),
        ),
    )
    manager = load_plugins(config, Path("/tmp"))
    names = {p.name for p in manager.plugins}
    assert names == {"wandb", "dvc", "docker", "ollama"}


def test_wandb_should_log_with_metadata() -> None:
    plugin = WandbPlugin(WandbPluginConfig(enabled=True, project="p"), Path("/tmp"))
    artifact = ArtifactConfig(
        type="evaluation",
        command="true",
        outputs=["out/"],
        metadata={"wandb": {"log_metrics": True}},
    )
    assert plugin.should_log(artifact) is True


def test_wandb_log_calls_wandb(tmp_path: Path) -> None:
    plugin = WandbPlugin(
        WandbPluginConfig(enabled=True, project="demo", entity="team"),
        tmp_path,
    )
    out = tmp_path / "out" / "metrics.json"
    out.parent.mkdir(parents=True)
    out.write_text("{}", encoding="utf-8")
    artifact = ArtifactConfig(
        type="evaluation",
        command="true",
        outputs=["out/metrics.json"],
        metadata={"wandb": {"log_metrics": True}},
    )
    mock_run = MagicMock()
    mock_wandb = MagicMock()
    mock_wandb.init.return_value = mock_run
    mock_wandb.Settings.return_value = MagicMock()
    mock_wandb.api.api_key = "test"

    with patch.dict("sys.modules", {"wandb": mock_wandb}):
        with patch.dict("os.environ", {"WANDB_API_KEY": "test-key"}):
            plugin.log(
                {
                    "artifact_config": artifact,
                    "artifact": "eval",
                    "metrics": {"accuracy": 0.9},
                    "outputs": ["out/metrics.json"],
                    "fingerprint": "abc",
                    "duration": 1.0,
                    "build_id": 1,
                    "success": True,
                }
            )

    mock_wandb.init.assert_called_once()
    mock_run.log.assert_called_once_with({"accuracy": 0.9})
    mock_run.finish.assert_called_once()


def test_dvc_should_pull_when_data_missing(tmp_path: Path) -> None:
    plugin = DvcPlugin(DvcPluginConfig(enabled=True), tmp_path)
    artifact = ArtifactConfig(
        type="dataset",
        source="data/train",
        metadata={"dvc": {"tracked": True}},
    )
    assert plugin.should_pull(artifact, rebuilding=False) is True


def test_dvc_pull_runs_cli(tmp_path: Path) -> None:
    plugin = DvcPlugin(DvcPluginConfig(enabled=True, remote="origin"), tmp_path)
    artifact = ArtifactConfig(
        type="dataset",
        source="data/train.dvc",
        metadata={"dvc": {"path": "data/train.dvc"}},
    )
    with patch("aimake.plugins.dvc.run_cli") as mock_run:
        with patch("aimake.plugins.dvc.require_cli", return_value="dvc"):
            path = plugin.pull(artifact, artifact_name="dataset")
    assert path == "data/train.dvc"
    mock_run.assert_called_once_with(
        ["dvc", "pull", "data/train.dvc", "-r", "origin"],
        cwd=tmp_path,
    )


def test_docker_wrap_command(tmp_path: Path) -> None:
    plugin = DockerPlugin(
        DockerPluginConfig(enabled=True, default_image="python:3.11"),
        tmp_path,
    )
    artifact = ArtifactConfig(
        type="generic",
        command="python train.py",
        outputs=["build/"],
        metadata={"docker": {"image": "myimg:latest", "workdir": "/workspace"}},
    )
    wrapped = plugin.wrap_command("train", artifact, "python train.py")
    assert wrapped.startswith("docker run --rm")
    assert "myimg:latest" in wrapped
    assert "python train.py" in wrapped


def test_docker_build_runs_cli(tmp_path: Path) -> None:
    plugin = DockerPlugin(DockerPluginConfig(enabled=True), tmp_path)
    artifact = ArtifactConfig(
        type="generic",
        command="true",
        outputs=["build/"],
        metadata={"docker": {"dockerfile": "Dockerfile", "image": "myimg:v1"}},
    )
    with patch("aimake.plugins.docker_plugin.run_cli") as mock_run:
        with patch("aimake.plugins.docker_plugin.require_cli", return_value="docker"):
            tag = plugin.build_image(artifact, artifact_name="train")
    assert tag == "myimg:v1"
    mock_run.assert_called_once()


def test_plugin_manager_wrap_command() -> None:
    manager = PluginManager()
    plugin = DockerPlugin(
        DockerPluginConfig(enabled=True, default_image="python:3.11"),
        Path("/tmp"),
    )
    manager.register(plugin)
    artifact = ArtifactConfig(
        type="generic",
        command="echo hi",
        outputs=["out/"],
        metadata={"docker": {"image": "img"}},
    )
    wrapped = manager.wrap_command("a", artifact, "echo hi")
    assert "docker run" in wrapped


def test_ollama_should_pull_when_missing(tmp_path: Path) -> None:
    plugin = OllamaPlugin(OllamaPluginConfig(enabled=True), tmp_path)
    artifact = ArtifactConfig(
        type="model",
        source="models/llm",
        metadata={"ollama": {"model": "llama3.2"}},
    )
    with patch.object(plugin, "model_exists", return_value=False):
        assert plugin.should_pull(artifact) is True


def test_ollama_pull_via_cli(tmp_path: Path) -> None:
    plugin = OllamaPlugin(OllamaPluginConfig(enabled=True), tmp_path)
    artifact = ArtifactConfig(
        type="model",
        source="models/llm",
        metadata={"ollama": {"model": "llama3.2", "tag": "latest"}},
    )
    with patch("aimake.plugins.ollama.run_cli") as mock_run:
        with patch("aimake.plugins.ollama.require_cli", return_value="ollama"):
            model = plugin.pull(artifact, artifact_name="llm")
    assert model == "llama3.2:latest"
    mock_run.assert_called_once()


def test_project_dvc_requires_plugin(tmp_path: Path) -> None:
    from aimake.project import Project

    (tmp_path / "aimake.yaml").write_text(
        """
project:
  name: t
artifacts:
  data:
    type: dataset
    source: data/x
""",
        encoding="utf-8",
    )
    project = Project.load(tmp_path / "aimake.yaml")
    with pytest.raises(ValueError, match="not enabled"):
        project.dvc_pull("data")
    project.close()


def test_project_ollama_pull(tmp_path: Path) -> None:
    from aimake.project import Project

    (tmp_path / "aimake.yaml").write_text(
        """
project:
  name: t
plugins:
  ollama:
    enabled: true
artifacts:
  llm:
    type: model
    source: models/llm
    metadata:
      ollama:
        model: llama3.2
""",
        encoding="utf-8",
    )
    project = Project.load(tmp_path / "aimake.yaml")
    plugin = project.plugin_manager.get("ollama")
    assert plugin is not None
    with patch.object(plugin, "pull", return_value="llama3.2") as mock_pull:
        model = project.ollama_pull("llm")
        mock_pull.assert_called_once()
        assert model == "llama3.2"
    project.close()
