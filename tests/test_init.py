"""Test project initialization."""

from pathlib import Path

from aimake.project import Project


def test_init_creates_files(tmp_path: Path) -> None:
    config_path = Project.init(tmp_path, name="my-project")
    assert config_path.exists()
    assert (tmp_path / ".aimake").is_dir()
    assert (tmp_path / "build").is_dir()
    assert (tmp_path / "aimake.yaml").exists()
    assert (tmp_path / "src" / "preprocess.py").exists()
    assert (tmp_path / "data" / "train.jsonl").exists()
    assert (tmp_path / "prompts" / "system.txt").exists()


def test_load_project(tmp_path: Path) -> None:
    Project.init(tmp_path)
    project = Project.load(tmp_path / "aimake.yaml")
    assert project.config.project.name == tmp_path.name or project.config.project.name
    assert len(project.graph) == 7
    project.close()
