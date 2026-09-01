"""Test metrics parsing and quality gates."""

from pathlib import Path

from aimake.config.schema import AimakeConfig, ArtifactConfig, ProjectConfig, QualityGateConfig
from aimake.metrics.parser import MetricsParser
from aimake.metrics.quality import QualityGateChecker


def _config_with_gates(gates: dict) -> AimakeConfig:
    return AimakeConfig(
        project=ProjectConfig(name="test"),
        artifacts={
            "eval": ArtifactConfig(type="evaluation", source="results.json"),
        },
        quality_gates=gates,
    )


def test_parse_metrics(tmp_path: Path) -> None:
    metrics_file = tmp_path / "results.json"
    metrics_file.write_text('{"accuracy": 0.912, "f1": 0.887, "latency_ms": 412}')

    parser = MetricsParser(tmp_path)
    metrics = parser.parse_file("results.json")
    assert metrics["accuracy"] == 0.912
    assert metrics["f1"] == 0.887


def test_quality_gate_pass() -> None:
    config = _config_with_gates({"accuracy": QualityGateConfig(minimum=0.9)})
    checker = QualityGateChecker(config)
    failures = checker.check({"accuracy": 0.95})
    assert len(failures) == 0


def test_quality_gate_fail() -> None:
    config = _config_with_gates({"accuracy": QualityGateConfig(minimum=0.9)})
    checker = QualityGateChecker(config)
    failures = checker.check({"accuracy": 0.84})
    assert len(failures) == 1
    assert failures[0].metric == "accuracy"


def test_quality_gate_maximum() -> None:
    config = _config_with_gates({"latency_ms": QualityGateConfig(maximum=500)})
    checker = QualityGateChecker(config)
    failures = checker.check({"latency_ms": 600})
    assert len(failures) == 1
