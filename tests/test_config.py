"""Test configuration loading and validation."""

from pathlib import Path

import pytest
import yaml

from aimake.config.loader import ConfigError, load_config, load_yaml
from aimake.config.schema import AimakeConfig
from aimake.config.validation import validate_config


MINIMAL_CONFIG = """
project:
  name: test
artifacts:
  data:
    type: dataset
    source: data.txt
"""


def test_load_valid_config(tmp_path: Path) -> None:
    config_file = tmp_path / "aimake.yaml"
    config_file.write_text(MINIMAL_CONFIG)
    config, path = load_config(config_file)
    assert config.project.name == "test"
    assert "data" in config.artifacts


def test_invalid_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "aimake.yaml"
    config_file.write_text(":\n  bad: [")
    with pytest.raises(ConfigError, match="Malformed YAML"):
        load_yaml(config_file)


def test_missing_artifacts(tmp_path: Path) -> None:
    config_file = tmp_path / "aimake.yaml"
    config_file.write_text("project:\n  name: test\nartifacts: {}")
    with pytest.raises(ConfigError):
        load_config(config_file)


def test_unknown_dependency(tmp_path: Path) -> None:
    config_file = tmp_path / "aimake.yaml"
    config_file.write_text("""
project:
  name: test
artifacts:
  a:
    type: dataset
    source: a.txt
    depends_on:
      - missing
""")
    with pytest.raises(ConfigError):
        load_config(config_file)


def test_invalid_artifact_type(tmp_path: Path) -> None:
    config_file = tmp_path / "aimake.yaml"
    config_file.write_text("""
project:
  name: test
artifacts:
  a:
    type: not_a_type
    source: a.txt
""")
    with pytest.raises(ConfigError):
        load_config(config_file)


def test_quality_gates_parsed(tmp_path: Path) -> None:
    config_file = tmp_path / "aimake.yaml"
    config_file.write_text(MINIMAL_CONFIG + """
quality_gates:
  accuracy:
    minimum: 0.9
""")
    config, _ = load_config(config_file)
    assert config.quality_gates["accuracy"].minimum == 0.9
