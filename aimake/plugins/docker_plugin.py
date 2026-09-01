"""Docker container execution plugin."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from aimake.config.schema import DockerPluginConfig
from aimake.plugins._cli import require_cli, run_cli
from aimake.plugins.base import AimakePlugin


class DockerPlugin(AimakePlugin):
    """Run artifact commands inside Docker containers."""

    name = "docker"
    version = "1.1.0"

    def __init__(self, config: DockerPluginConfig, project_root: Path) -> None:
        self.config = config
        self.project_root = project_root

    def on_pre_artifact(self, context: dict[str, Any]) -> None:
        artifact_config = context.get("artifact_config")
        if artifact_config is None:
            return
        meta = self.docker_metadata(artifact_config)
        if meta and self.config.auto_build and meta.get("dockerfile"):
            self.build_image(artifact_config, artifact_name=context.get("artifact", ""))

    def wrap_command(self, artifact: str, artifact_config, command: str) -> str:
        meta = self.docker_metadata(artifact_config)
        if not meta:
            return command
        image = meta.get("image") or self.config.default_image
        if not image:
            return command
        return self._docker_run(command, meta)

    @staticmethod
    def docker_metadata(artifact_config) -> dict[str, Any] | None:
        meta = artifact_config.metadata.get("docker")
        return meta if isinstance(meta, dict) else None

    def build_image(
        self,
        artifact_config,
        *,
        artifact_name: str = "",
        tag: str | None = None,
    ) -> str:
        meta = self.docker_metadata(artifact_config)
        if not meta or not meta.get("dockerfile"):
            raise ValueError(f"Artifact '{artifact_name}' has no docker.dockerfile configured")

        require_cli("docker", extra="docker")
        dockerfile = meta["dockerfile"]
        context = meta.get("build_context", ".")
        image_tag = tag or meta.get("image") or self.config.default_image
        if not image_tag:
            raise ValueError("Docker image tag is required for build")

        cmd = [
            "docker",
            "build",
            "-f",
            dockerfile,
            "-t",
            image_tag,
            context,
        ]
        for key, value in (meta.get("build_args") or {}).items():
            cmd.extend(["--build-arg", f"{key}={value}"])

        run_cli(cmd, cwd=self.project_root)
        return image_tag

    def status(self, artifact_config) -> dict[str, Any]:
        meta = self.docker_metadata(artifact_config)
        if not meta:
            return {"linked": False}
        image = meta.get("image") or self.config.default_image
        out: dict[str, Any] = {
            "linked": True,
            "image": image,
            "dockerfile": meta.get("dockerfile"),
            "build_context": meta.get("build_context", "."),
            "gpu": meta.get("gpu", self.config.gpu),
        }
        if image:
            try:
                require_cli("docker", extra="docker")
                result = run_cli(
                    ["docker", "image", "inspect", image],
                    cwd=self.project_root,
                    check=False,
                )
                out["image_exists"] = result.returncode == 0
            except ImportError:
                out["image_exists"] = None
        return out

    def _docker_run(self, command: str, meta: dict[str, Any]) -> str:
        require_cli("docker", extra="docker")
        image = meta.get("image") or self.config.default_image
        if not image:
            raise ValueError("Docker image is required in metadata.docker.image or plugins.docker.default_image")

        parts = ["docker", "run", "--rm"]
        if meta.get("gpu", self.config.gpu):
            parts.extend(["--gpus", "all"])

        network = meta.get("network") or self.config.network
        if network:
            parts.extend(["--network", network])

        volumes = meta.get("volumes")
        if volumes is None:
            volumes = [f"{self.project_root.resolve()}:/workspace"]
        for volume in volumes:
            parts.extend(["-v", volume])

        workdir = meta.get("workdir", "/workspace")
        parts.extend(["-w", workdir])

        for key, value in (meta.get("env") or {}).items():
            parts.extend(["-e", f"{key}={value}"])

        parts.append(image)
        parts.append("bash")
        parts.append("-lc")
        parts.append(command)
        return " ".join(shlex.quote(p) for p in parts)
