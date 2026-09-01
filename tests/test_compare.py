"""Tests for experiment comparison."""

import json

from aimake.cache.store import Cache
from aimake.config.schema import AimakeConfig, ArtifactConfig, ProjectConfig
from aimake.experiments.compare import CompareEngine
from aimake.state.database import StateDatabase


def _seed_builds(db: StateDatabase) -> tuple[int, int]:
    b1 = db.start_build(parameters={"temperature": 0.8})
    db.finish_build(
        b1,
        duration=1.0,
        status="success",
        changed=["eval"],
        rebuilt=["eval"],
        reused=[],
        failed=[],
        metrics={"accuracy": 0.85, "latency_ms": 500},
    )
    b2 = db.start_build(parameters={"temperature": 1.2})
    db.finish_build(
        b2,
        duration=1.2,
        status="success",
        changed=["eval"],
        rebuilt=["eval"],
        reused=[],
        failed=[],
        metrics={"accuracy": 0.91, "latency_ms": 450},
    )
    return b1, b2


def test_compare_latest_vs_previous(tmp_path) -> None:
    db = StateDatabase(tmp_path / ".aimake")
    b1, b2 = _seed_builds(db)

    engine = CompareEngine(db)
    result = engine.compare("previous", "latest", higher_is_better={"accuracy"}, lower_is_better={"latency_ms"})

    assert result.baseline_id == b1
    assert result.candidate_id == b2
    assert result.baseline_metrics["accuracy"] == 0.85
    assert result.candidate_metrics["accuracy"] == 0.91
    assert result.parameter_changes["temperature"] == (0.8, 1.2)
    accuracy_delta = next(d for d in result.metric_deltas if d.name == "accuracy")
    assert accuracy_delta.delta == 0.06
    assert accuracy_delta.improved is True
    db.close()


def test_compare_build_ids(tmp_path) -> None:
    db = StateDatabase(tmp_path / ".aimake")
    b1, b2 = _seed_builds(db)
    engine = CompareEngine(db)
    result = engine.compare(b1, b2)
    assert result.has_metric_changes
    db.close()


def test_project_compare_api(tmp_path) -> None:
    from aimake.project import Project

    (tmp_path / "aimake.yaml").write_text(
        """
project:
  name: t
artifacts:
  eval:
    type: evaluation
    source: x.json
quality_gates:
  accuracy:
    minimum: 0.8
"""
    )
    project = Project.load(tmp_path / "aimake.yaml")
    b1, b2 = _seed_builds(project.cache.state_db)
    result = project.compare_builds(b1, b2)
    assert result.candidate_id == b2
    project.close()
