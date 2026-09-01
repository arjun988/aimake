"""Tests for cache configuration."""

import pytest

from aimake.config.schema import AimakeConfig, ArtifactConfig, RemoteCacheConfig, S3CacheConfig


def test_s3_cache_config_requires_s3_block() -> None:
    with pytest.raises(ValueError, match="requires an 's3'"):
        RemoteCacheConfig(type="s3")


def test_s3_cache_config_valid() -> None:
    cfg = RemoteCacheConfig(
        type="s3",
        s3=S3CacheConfig(bucket="my-bucket", prefix="cache/"),
    )
    assert cfg.s3.bucket == "my-bucket"


def test_artifact_resource_config() -> None:
    config = AimakeConfig(
        artifacts={
            "embed": ArtifactConfig(
                type="embedding",
                source="x.txt",
                resources={"gpu": 1},
            ),
        },
    )
    assert config.artifacts["embed"].resources.gpu == 1
