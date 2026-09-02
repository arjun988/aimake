"""Secrets loading: .env + Vault / Doppler / 1Password CLI providers."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from aimake.config.schema import SecretsConfig, SecretsProviderConfig

_ENV_LINE = re.compile(
    r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$"
)


def parse_dotenv(text: str) -> dict[str, str]:
    """Parse KEY=VALUE lines from a .env file body."""
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _ENV_LINE.match(line)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()
        result[key] = value
    return result


def load_dotenv_file(path: Path, *, override: bool = False) -> dict[str, str]:
    """Load a .env file into os.environ. Returns keys that were set."""
    if not path.is_file():
        return {}
    loaded = parse_dotenv(path.read_text(encoding="utf-8"))
    applied: dict[str, str] = {}
    for key, value in loaded.items():
        if override or key not in os.environ:
            os.environ[key] = value
            applied[key] = value
    return applied


def _run_json(cmd: list[str]) -> Any:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"{' '.join(cmd[:2])} failed: {err or proc.returncode}")
    return json.loads(proc.stdout or "{}")


def load_vault(provider: SecretsProviderConfig) -> dict[str, str]:
    if not shutil.which("vault"):
        raise RuntimeError("Vault CLI not found on PATH")
    if not provider.path:
        raise RuntimeError("secrets provider vault requires 'path'")
    data = _run_json(["vault", "kv", "get", "-format=json", provider.path])
    secrets = data.get("data", {}).get("data") or data.get("data") or {}
    return {str(k): str(v) for k, v in secrets.items()}


def load_doppler(provider: SecretsProviderConfig) -> dict[str, str]:
    if not shutil.which("doppler"):
        raise RuntimeError("Doppler CLI not found on PATH")
    cmd = ["doppler", "secrets", "download", "--no-file", "--format", "json"]
    if provider.project:
        cmd.extend(["--project", provider.project])
    if provider.config:
        cmd.extend(["--config", provider.config])
    data = _run_json(cmd)
    return {str(k): str(v) for k, v in data.items() if not str(k).startswith("DOPPLER_")}


def load_onepassword(provider: SecretsProviderConfig) -> dict[str, str]:
    if not shutil.which("op"):
        raise RuntimeError("1Password CLI (op) not found on PATH")
    if not provider.item:
        raise RuntimeError("secrets provider onepassword requires 'item'")
    ref = provider.item
    if provider.vault:
        ref = f"{provider.vault}/{provider.item}"
    data = _run_json(["op", "item", "get", ref, "--format", "json"])
    result: dict[str, str] = {}
    for field in data.get("fields") or []:
        label = field.get("label") or field.get("id")
        value = field.get("value")
        if label and value is not None:
            result[str(label)] = str(value)
    return result


def apply_secrets(values: dict[str, str], *, override: bool = False) -> dict[str, str]:
    applied: dict[str, str] = {}
    for key, value in values.items():
        if override or key not in os.environ:
            os.environ[key] = value
            applied[key] = value
    return applied


def load_secrets(
    project_root: Path,
    config: SecretsConfig | None,
) -> dict[str, Any]:
    """Load .env and configured providers into the environment.

    Returns a summary for doctor / logging (never includes secret values).
    """
    cfg = config or SecretsConfig()
    summary: dict[str, Any] = {"dotenv": [], "providers": []}

    if cfg.dotenv:
        env_path = (
            Path(cfg.dotenv_path)
            if cfg.dotenv_path
            else project_root / ".env"
        )
        if not env_path.is_absolute():
            env_path = project_root / env_path
        keys = list(load_dotenv_file(env_path).keys())
        summary["dotenv"] = keys

    for provider in cfg.providers:
        ptype = provider.type.lower()
        try:
            if ptype == "vault":
                values = load_vault(provider)
            elif ptype == "doppler":
                values = load_doppler(provider)
            elif ptype in ("onepassword", "1password", "op"):
                values = load_onepassword(provider)
            elif ptype == "env":
                values = {}
            else:
                raise RuntimeError(f"Unknown secrets provider type: {ptype}")
            applied = apply_secrets(values)
            summary["providers"].append(
                {"type": ptype, "keys": sorted(applied.keys()), "ok": True}
            )
        except Exception as e:
            summary["providers"].append(
                {"type": ptype, "ok": False, "error": str(e)}
            )
    return summary
