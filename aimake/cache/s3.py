"""S3 remote cache backend."""

from __future__ import annotations

import io
import json
import shutil
import tarfile
import tempfile
import threading
from pathlib import Path
from typing import Any

from aimake.config.schema import S3CacheConfig
from aimake.hashing.files import strip_prefix


class S3CacheError(Exception):
    """Raised when S3 cache operations fail."""


class S3Cache:
    """Content-addressable cache backed by Amazon S3 (or S3-compatible storage)."""

    def __init__(self, config: S3CacheConfig) -> None:
        self.config = config
        self._client = None
        self._lock = threading.Lock()

    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
            except ImportError as e:
                raise S3CacheError(
                    "boto3 is required for S3 cache. Install with: pip install aimake[s3]"
                ) from e

            session_kwargs: dict[str, Any] = {}
            if self.config.region:
                session_kwargs["region_name"] = self.config.region
            session = boto3.session.Session(**session_kwargs)
            client_kwargs: dict[str, Any] = {}
            if self.config.endpoint_url:
                client_kwargs["endpoint_url"] = self.config.endpoint_url
            self._client = session.client("s3", **client_kwargs)
        return self._client

    def _key(self, fingerprint: str, *parts: str) -> str:
        prefix = self.config.prefix.rstrip("/")
        fp = strip_prefix(fingerprint)
        path = "/".join([prefix, fp, *parts])
        return path.lstrip("/")

    def _archive_key(self, fingerprint: str) -> str:
        return self._key(fingerprint, "entry.tar.gz")

    def has(self, fingerprint: str) -> bool:
        try:
            self.client.head_object(
                Bucket=self.config.bucket,
                Key=self._archive_key(fingerprint),
            )
            return True
        except Exception:
            return False

    def get(self, fingerprint: str) -> dict[str, Any] | None:
        if not self.has(fingerprint):
            return None
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir) / "entry.tar.gz"
            self._download_archive(fingerprint, archive)
            meta = self._read_metadata_from_archive(archive)
            return meta

    def store(
        self,
        fingerprint: str,
        artifact_name: str,
        outputs: list[str],
        project_root: Path,
        *,
        command: str | None = None,
        duration: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                entry = tmp / "entry"
                artifacts_dir = entry / "artifacts"
                artifacts_dir.mkdir(parents=True)

                stored_outputs: list[str] = []
                for output in outputs:
                    src = project_root / output
                    if src.exists():
                        dest = artifacts_dir / output.replace("/", "_").replace("\\", "_")
                        if src.is_dir():
                            shutil.copytree(src, dest, dirs_exist_ok=True)
                        else:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, dest)
                        stored_outputs.append(output)

                meta = {
                    "fingerprint": fingerprint,
                    "artifact": artifact_name,
                    "outputs": stored_outputs,
                    "command": command,
                    "duration": duration,
                    "metadata": metadata or {},
                }
                with open(entry / "metadata.json", "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)

                archive = tmp / "entry.tar.gz"
                self._create_archive(entry, archive)
                self._upload_archive(fingerprint, archive)

    def restore(self, fingerprint: str, outputs: list[str], project_root: Path) -> bool:
        if not self.has(fingerprint):
            return False

        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir) / "entry.tar.gz"
            entry = Path(tmpdir) / "entry"
            self._download_archive(fingerprint, archive)
            self._extract_archive(archive, entry)

            meta_path = entry / "metadata.json"
            if not meta_path.is_file():
                return False
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)

            artifacts_dir = entry / "artifacts"
            for output in outputs:
                cache_name = output.replace("/", "_").replace("\\", "_")
                src = artifacts_dir / cache_name
                dest = project_root / output
                if src.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if src.is_dir():
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(src, dest)
                    else:
                        shutil.copy2(src, dest)
            return True

    def remove(self, fingerprint: str) -> None:
        if not self.has(fingerprint):
            return
        self.client.delete_object(
            Bucket=self.config.bucket,
            Key=self._archive_key(fingerprint),
        )

    def clear(self) -> None:
        prefix = self.config.prefix.rstrip("/") + "/"
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.config.bucket, Prefix=prefix):
            objects = page.get("Contents", [])
            if not objects:
                continue
            self.client.delete_objects(
                Bucket=self.config.bucket,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
            )

    def verify(self, fingerprint: str) -> bool:
        meta = self.get(fingerprint)
        return meta is not None

    def list_entries(self) -> list[str]:
        prefix = self.config.prefix.rstrip("/") + "/"
        entries: set[str] = set()
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.config.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                rel = key[len(prefix):] if key.startswith(prefix) else key
                parts = rel.split("/")
                if len(parts) >= 1 and parts[0]:
                    entries.add(parts[0])
        return sorted(entries)

    def pull(self, fingerprint: str, local_cache: "FilesystemCache") -> bool:
        """Download remote entry into local filesystem cache."""
        from aimake.cache.filesystem import FilesystemCache

        if not isinstance(local_cache, FilesystemCache):
            return False
        if local_cache.has(fingerprint):
            return True
        if not self.has(fingerprint):
            return False

        meta = self.get(fingerprint)
        if not meta:
            return False

        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir) / "entry.tar.gz"
            entry = Path(tmpdir) / "entry"
            self._download_archive(fingerprint, archive)
            self._extract_archive(archive, entry)

            # Populate local cache via FilesystemCache.store from extracted outputs
            outputs = meta.get("outputs", [])
            # Write extracted artifacts back through a temp project layout
            temp_project = Path(tmpdir) / "project"
            temp_project.mkdir()
            artifacts_dir = entry / "artifacts"
            restore_outputs = []
            for output in outputs:
                cache_name = output.replace("/", "_").replace("\\", "_")
                src = artifacts_dir / cache_name
                if src.exists():
                    dest = temp_project / output
                    if src.is_dir():
                        shutil.copytree(src, dest, dirs_exist_ok=True)
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dest)
                    restore_outputs.append(output)

            local_cache.store(
                fingerprint,
                meta.get("artifact", "unknown"),
                restore_outputs,
                temp_project,
                command=meta.get("command"),
                duration=meta.get("duration"),
                metadata=meta.get("metadata"),
            )
        return True

    def push(self, fingerprint: str, local_cache: "FilesystemCache") -> bool:
        """Upload a local cache entry to S3."""
        from aimake.cache.filesystem import FilesystemCache

        if not isinstance(local_cache, FilesystemCache):
            return False
        if not local_cache.has(fingerprint):
            return False
        if self.has(fingerprint):
            return True

        meta = local_cache.get(fingerprint)
        if not meta:
            return False

        fp_dir = local_cache._entry_dir(fingerprint)
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir) / "entry.tar.gz"
            self._create_archive(fp_dir, archive)
            self._upload_archive(fingerprint, archive)
        return True

    def _upload_archive(self, fingerprint: str, archive: Path) -> None:
        with open(archive, "rb") as f:
            self.client.upload_fileobj(f, self.config.bucket, self._archive_key(fingerprint))

    def _download_archive(self, fingerprint: str, dest: Path) -> None:
        with open(dest, "wb") as f:
            self.client.download_fileobj(self.config.bucket, self._archive_key(fingerprint), f)

    @staticmethod
    def _create_archive(source_dir: Path, archive: Path) -> None:
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(source_dir, arcname="entry")

    @staticmethod
    def _extract_archive(archive: Path, dest: Path) -> None:
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(dest.parent)
        # tar adds 'entry' subdir under dest.parent

    @staticmethod
    def _read_metadata_from_archive(archive: Path) -> dict[str, Any] | None:
        with tarfile.open(archive, "r:gz") as tar:
            try:
                member = tar.getmember("entry/metadata.json")
            except KeyError:
                return None
            f = tar.extractfile(member)
            if f is None:
                return None
            return json.load(f)
