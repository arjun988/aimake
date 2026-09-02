"""Tests for team features: policy, schedule, secrets, --project, lock remote."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from aimake.config.loader import resolve_project_config, ConfigError
from aimake.config.schema import (
    AimakeConfig,
    ArtifactConfig,
    PolicyConfig,
    PromotePolicyConfig,
    QualityGateConfig,
    SecretsConfig,
)
from aimake.lock import generate_lock, lock_fingerprints, remote_identity
from aimake.policy import PolicyError, PromotePolicyChecker
from aimake.schedule import CronError, CronSchedule, next_matches
from aimake.secrets import parse_dotenv, load_dotenv_file


def _cfg(**kwargs) -> AimakeConfig:
    artifacts = kwargs.pop(
        "artifacts",
        {"eval": ArtifactConfig(type="evaluation", command="echo 1", outputs=["out.json"])},
    )
    return AimakeConfig(artifacts=artifacts, **kwargs)


def test_promote_policy_blocks_low_accuracy() -> None:
    config = _cfg(
        policy=PolicyConfig(
            promote=PromotePolicyConfig(
                stages=["production"],
                metrics={"accuracy": QualityGateConfig(minimum=0.9, required=True)},
                max_cost_usd=1.0,
            )
        )
    )
    checker = PromotePolicyChecker(config)
    violations = checker.check(
        stage="production",
        metrics={"accuracy": 0.5, "cost_usd": 0.2},
        tags=[],
        cost_usd=0.2,
    )
    assert any(v.code == "metric" for v in violations)
    with pytest.raises(PolicyError):
        checker.enforce(
            stage="production",
            metrics={"accuracy": 0.5},
            cost_usd=0.2,
        )


def test_promote_policy_skips_ungated_stage() -> None:
    config = _cfg(
        policy=PolicyConfig(
            promote=PromotePolicyConfig(
                stages=["production"],
                metrics={"accuracy": QualityGateConfig(minimum=0.9)},
            )
        )
    )
    assert PromotePolicyChecker(config).check(stage="staging", metrics={"accuracy": 0.1}) == []


def test_cron_daily_six_am() -> None:
    sched = CronSchedule.parse("0 6 * * *")
    dt = datetime(2026, 9, 2, 6, 0, tzinfo=timezone.utc)
    assert sched.matches(dt)
    assert not sched.matches(dt.replace(hour=7))
    nxt = next_matches(sched, datetime(2026, 9, 2, 5, 0, tzinfo=timezone.utc))
    assert nxt.hour == 6 and nxt.minute == 0


def test_cron_invalid() -> None:
    with pytest.raises(CronError):
        CronSchedule.parse("0 6 *")


def test_dotenv_parse_and_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text("FOO=bar\n# comment\nEXPORT_BAZ='qux'\n", encoding="utf-8")
    parsed = parse_dotenv(env.read_text(encoding="utf-8"))
    assert parsed["FOO"] == "bar"
    monkeypatch.delenv("FOO", raising=False)
    applied = load_dotenv_file(env)
    assert applied["FOO"] == "bar"


def test_resolve_project_monorepo(tmp_path: Path) -> None:
    sub = tmp_path / "apps" / "rag"
    sub.mkdir(parents=True)
    (sub / "aimake.yaml").write_text(
        yaml.dump(
            {
                "project": {"name": "rag"},
                "artifacts": {
                    "data": {"type": "dataset", "source": "data/"},
                },
            }
        ),
        encoding="utf-8",
    )
    resolved = resolve_project_config(project=str(sub))
    assert resolved is not None
    assert resolved.name == "aimake.yaml"
    with pytest.raises(ConfigError):
        resolve_project_config(config=Path("x"), project="y")


def test_lock_includes_remote_identity() -> None:
    from aimake.config.schema import RemoteCacheConfig, S3CacheConfig

    remote = RemoteCacheConfig(
        type="s3",
        team_id="acme",
        s3=S3CacheConfig(bucket="caches", prefix="aimake/cache/"),
    )
    data = generate_lock("demo", {"a": "sha256:abc"}, remote=remote_identity(remote))
    assert data["version"] == 2
    assert data["cache"]["remote"]["team_id"] == "acme"
    assert "acme" in data["cache"]["remote"]["prefix"]
    assert lock_fingerprints(data)["a"] == "sha256:abc"
