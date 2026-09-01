"""DVC data versioning plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aimake.config.schema import DvcPluginConfig
from aimake.plugins._cli import require_cli, run_cli
from aimake.plugins.base import AimakePlugin


class DvcPlugin(AimakePlugin):
    """Pull and push DVC-tracked data."""

    name = "dvc"
    version = "1.1.0"

    def __init__(self, config: DvcPluginConfig, project_root: Path) -> None:
        self.config = config
        self.project_root = project_root

    def on_pre_artifact(self, context: dict[str, Any]) -> None:
        artifact_config = context.get("artifact_config")
        if artifact_config is None:
            return
        if self.should_pull(artifact_config, rebuilding=context.get("rebuilding", False)):
            self.pull(artifact_config, artifact_name=context.get("artifact", ""))

    def on_artifact_complete(self, context: dict[str, Any]) -> None:
        artifact_config = context.get("artifact_config")
        if artifact_config is None or not context.get("success", True):
            return
        if self.should_push(artifact_config):
            self.push(artifact_config, artifact_name=context.get("artifact", ""))

    @staticmethod
    def dvc_metadata(artifact_config) -> dict[str, Any] | None:
        meta = artifact_config.metadata.get("dvc")
        if isinstance(meta, dict) and meta.get("path"):
            return meta
        if isinstance(meta, dict) and meta.get("tracked"):
            return meta
        if artifact_config.source and (
            artifact_config.source.endswith(".dvc")
            or (meta and meta.get("tracked"))
        ):
            return {"path": artifact_config.source, **(meta or {})}
        return meta if isinstance(meta, dict) and meta.get("tracked") else None

    def tracked_path(self, artifact_config) -> str | None:
        meta = self.dvc_metadata(artifact_config)
        if meta and meta.get("path"):
            return meta["path"]
        if artifact_config.source:
            src = artifact_config.source
            dvc_file = self.project_root / f"{src}.dvc"
            if dvc_file.is_file() or src.endswith(".dvc"):
                return src if src.endswith(".dvc") else f"{src}.dvc"
            if (self.project_root / src).exists() or meta:
                return src
        for output in artifact_config.outputs:
            dvc_file = self.project_root / f"{output}.dvc"
            if dvc_file.is_file():
                return f"{output}.dvc"
            if (self.project_root / output).exists():
                return output
        return None

    def should_pull(self, artifact_config, *, rebuilding: bool = False) -> bool:
        meta = self.dvc_metadata(artifact_config)
        path = self.tracked_path(artifact_config)
        if not path and not meta:
            return False
        if meta and meta.get("pull") is False:
            return False
        if not self.config.auto_pull and not (meta and meta.get("pull") is True):
            return False
        if meta and meta.get("pull") == "always" and rebuilding:
            return True
        if rebuilding and meta and meta.get("pull", True) is not False:
            return True
        return self._data_missing(path)

    def should_push(self, artifact_config) -> bool:
        meta = self.dvc_metadata(artifact_config)
        if not meta and not self.tracked_path(artifact_config):
            return False
        if meta and meta.get("push") is True:
            return True
        return self.config.auto_push and (not meta or meta.get("push") is not False)

    def pull(self, artifact_config, *, artifact_name: str = "") -> str:
        path = self.tracked_path(artifact_config)
        if not path:
            raise ValueError(f"Artifact '{artifact_name}' has no DVC path configured")
        require_cli("dvc", extra="dvc")
        remote = self._remote(artifact_config)
        cmd = ["dvc", "pull", path]
        if remote:
            cmd.extend(["-r", remote])
        run_cli(cmd, cwd=self.project_root)
        return path

    def push(self, artifact_config, *, artifact_name: str = "") -> str:
        path = self.tracked_path(artifact_config)
        if not path:
            raise ValueError(f"Artifact '{artifact_name}' has no DVC path configured")
        require_cli("dvc", extra="dvc")
        remote = self._remote(artifact_config)
        cmd = ["dvc", "push", path]
        if remote:
            cmd.extend(["-r", remote])
        run_cli(cmd, cwd=self.project_root)
        return path

    def status(self, artifact_config) -> dict[str, Any]:
        path = self.tracked_path(artifact_config)
        meta = self.dvc_metadata(artifact_config) or {}
        if not path:
            return {"linked": False}
        local = self.project_root / path.replace(".dvc", "")
        dvc_file = self.project_root / path if path.endswith(".dvc") else self.project_root / f"{path}.dvc"
        out: dict[str, Any] = {
            "linked": True,
            "path": path,
            "remote": self._remote(artifact_config),
            "dvc_file": str(dvc_file) if dvc_file.is_file() else None,
            "local_exists": local.exists(),
            "auto_pull": self.config.auto_pull,
            "auto_push": self.config.auto_push,
        }
        try:
            require_cli("dvc", extra="dvc")
            result = run_cli(
                ["dvc", "status", path, "--json"],
                cwd=self.project_root,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                out["dvc_status"] = result.stdout.strip()[:500]
        except ImportError:
            out["dvc_status"] = "dvc not installed"
        return out

    def _remote(self, artifact_config) -> str | None:
        meta = self.dvc_metadata(artifact_config) or {}
        return meta.get("remote") or self.config.remote

    def _data_missing(self, path: str | None) -> bool:
        if not path:
            return False
        if path.endswith(".dvc"):
            target = path[:-4]
            return not (self.project_root / target).exists()
        target_path = self.project_root / path
        if target_path.is_file():
            return not target_path.exists()
        if target_path.is_dir():
            return not any(target_path.iterdir()) if target_path.exists() else True
        dvc_file = self.project_root / f"{path}.dvc"
        if dvc_file.is_file():
            return not target_path.exists()
        return not target_path.exists()
