"""Push registry versions to remote backends (S3 / Hugging Face / W&B)."""

from __future__ import annotations

import json
import os
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aimake.config.schema import RegistryConfig, RegistryRemoteConfig
from aimake.registry.store import RegistryEntry


@dataclass
class RegistryPushResult:
    backend: str
    uri: str
    ok: bool
    detail: str = ""


class RegistryRemoteError(Exception):
    """Remote registry push failed."""


class RegistryRemote:
    """Push a registry entry's outputs + metadata to a remote store."""

    def __init__(self, config: RegistryConfig, project_root: Path) -> None:
        self.config = config
        self.remote: RegistryRemoteConfig | None = config.remote
        self.project_root = project_root

    @property
    def enabled(self) -> bool:
        return self.remote is not None

    def push(
        self,
        entry: RegistryEntry,
        outputs: list[str] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> RegistryPushResult:
        if not self.remote:
            raise RegistryRemoteError("No registry.remote configured")
        t = self.remote.type
        if t == "s3":
            return self._push_s3(entry, outputs or [], metadata or {})
        if t == "huggingface":
            return self._push_hf(entry, outputs or [], metadata or {})
        if t == "wandb":
            return self._push_wandb(entry, outputs or [], metadata or {})
        raise RegistryRemoteError(f"Unsupported registry remote type: {t}")

    def _manifest(
        self,
        entry: RegistryEntry,
        outputs: list[str],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "artifact_name": entry.artifact_name,
            "version": entry.version,
            "fingerprint": entry.fingerprint,
            "stage": entry.stage,
            "tags": entry.tags,
            "metrics": entry.metrics,
            "build_id": entry.build_id,
            "outputs": outputs,
            "metadata": metadata,
        }

    def _pack_outputs(self, outputs: list[str], dest: Path) -> list[str]:
        packed: list[str] = []
        with tarfile.open(dest, "w:gz") as tar:
            for rel in outputs:
                path = (self.project_root / rel).resolve()
                if not path.exists():
                    continue
                arcname = Path(rel).as_posix()
                tar.add(path, arcname=arcname)
                packed.append(rel)
        return packed

    def _push_s3(
        self,
        entry: RegistryEntry,
        outputs: list[str],
        metadata: dict[str, Any],
    ) -> RegistryPushResult:
        assert self.remote and self.remote.s3
        cfg = self.remote.s3
        try:
            import boto3
        except ImportError as e:
            raise RegistryRemoteError(
                "boto3 required for registry S3 push. pip install aimake[s3]"
            ) from e

        session_kwargs: dict[str, Any] = {}
        if cfg.region:
            session_kwargs["region_name"] = cfg.region
        client_kwargs: dict[str, Any] = {}
        if cfg.endpoint_url:
            client_kwargs["endpoint_url"] = cfg.endpoint_url
        client = boto3.session.Session(**session_kwargs).client("s3", **client_kwargs)

        prefix = cfg.prefix.rstrip("/")
        base = f"{prefix}/{entry.artifact_name}/{entry.version}".lstrip("/")

        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "artifacts.tar.gz"
            packed = self._pack_outputs(outputs, archive)
            manifest = self._manifest(entry, packed, metadata)
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            client.upload_file(str(manifest_path), cfg.bucket, f"{base}/manifest.json")
            if packed:
                client.upload_file(str(archive), cfg.bucket, f"{base}/artifacts.tar.gz")

        uri = f"s3://{cfg.bucket}/{base}/"
        return RegistryPushResult(backend="s3", uri=uri, ok=True, detail=f"{len(packed)} files")

    def _push_hf(
        self,
        entry: RegistryEntry,
        outputs: list[str],
        metadata: dict[str, Any],
    ) -> RegistryPushResult:
        assert self.remote and self.remote.huggingface
        cfg = self.remote.huggingface
        try:
            from huggingface_hub import HfApi
        except ImportError as e:
            raise RegistryRemoteError(
                "huggingface_hub required. pip install aimake[huggingface]"
            ) from e

        token = os.environ.get(cfg.token_env)
        api = HfApi(token=token)
        repo_id = cfg.repo_id
        api.create_repo(repo_id, private=cfg.private, exist_ok=True, repo_type="model")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._manifest(entry, outputs, metadata)
            (root / "aimake-manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
            for rel in outputs:
                src = self.project_root / rel
                if src.is_file():
                    dest = root / Path(rel).name
                    dest.write_bytes(src.read_bytes())
                elif src.is_dir():
                    # upload folder separately
                    api.upload_folder(
                        folder_path=str(src),
                        path_in_repo=f"{entry.version}/{Path(rel).name}",
                        repo_id=repo_id,
                        repo_type="model",
                    )
            api.upload_folder(
                folder_path=str(root),
                path_in_repo=entry.version,
                repo_id=repo_id,
                repo_type="model",
            )

        uri = f"hf://{repo_id}@{entry.version}"
        return RegistryPushResult(backend="huggingface", uri=uri, ok=True)

    def _push_wandb(
        self,
        entry: RegistryEntry,
        outputs: list[str],
        metadata: dict[str, Any],
    ) -> RegistryPushResult:
        assert self.remote and self.remote.wandb
        cfg = self.remote.wandb
        try:
            import wandb
        except ImportError as e:
            raise RegistryRemoteError(
                "wandb required. pip install aimake[wandb]"
            ) from e

        api_key = os.environ.get(cfg.api_key_env)
        if api_key:
            wandb.login(key=api_key, relogin=False)

        run = wandb.init(
            project=cfg.project or "aimake",
            entity=cfg.entity,
            job_type="registry-push",
            name=f"{entry.artifact_name}-{entry.version}",
            config=self._manifest(entry, outputs, metadata),
            reinit=True,
        )
        art = wandb.Artifact(
            name=f"{entry.artifact_name}-{entry.version}",
            type=cfg.type,
            metadata={
                "fingerprint": entry.fingerprint,
                "stage": entry.stage,
                "tags": entry.tags,
            },
        )
        for rel in outputs:
            path = self.project_root / rel
            if path.is_file():
                art.add_file(str(path), name=Path(rel).name)
            elif path.is_dir():
                art.add_dir(str(path), name=Path(rel).name)
        run.log_artifact(art)
        aliases = list({entry.stage, *entry.tags, entry.version})
        art.wait()
        try:
            art.link(
                f"{cfg.entity + '/' if cfg.entity else ''}{cfg.project or 'aimake'}/{entry.artifact_name}",
                aliases=aliases,
            )
        except Exception:
            # link is best-effort (Model Registry may need org setup)
            pass
        uri = f"wandb://{cfg.project or 'aimake'}/{entry.artifact_name}:{entry.version}"
        run.finish()
        return RegistryPushResult(backend="wandb", uri=uri, ok=True)
