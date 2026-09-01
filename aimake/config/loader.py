"""Load and parse aimake.yaml configuration files."""

from __future__ import annotations

from pathlib import Path

import yaml

from aimake.config.schema import AimakeConfig
from aimake.constants import CONFIG_FILE


class ConfigError(Exception):
    """Raised when configuration cannot be loaded or parsed."""


def find_config(start: Path | None = None) -> Path:
    """Locate aimake.yaml by walking up from start directory."""
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        config_path = directory / CONFIG_FILE
        if config_path.is_file():
            return config_path
    raise ConfigError(
        f"Could not find {CONFIG_FILE}. Run 'aimake init' to create a project."
    )


def load_yaml(path: Path) -> dict:
    """Load raw YAML from a file."""
    if not path.is_file():
        raise ConfigError(f"Configuration file not found: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Malformed YAML in {path}: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"Configuration must be a YAML mapping, got {type(data).__name__}")
    return data


def load_config(path: Path | None = None) -> tuple[AimakeConfig, Path]:
    """Load and validate configuration from aimake.yaml."""
    config_path = path if path else find_config()
    config_path = config_path.resolve()
    raw = load_yaml(config_path)
    try:
        config = AimakeConfig.model_validate(raw)
    except Exception as e:
        raise ConfigError(f"Invalid configuration: {e}") from e
    return config, config_path


def save_yaml(path: Path, data: dict) -> None:
    """Save a dictionary as YAML."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
