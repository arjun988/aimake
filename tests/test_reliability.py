"""Tests for volatile deps, atomic outputs, validation, and plan cost estimates."""

from pathlib import Path

import pytest

from aimake.cache.store import Cache
from aimake.config.schema import (
    AimakeConfig,
    ArtifactConfig,
    CostEstimateConfig,
    ExternalDependencyConfig,
    OutputValidationConfig,
    ProjectConfig,
    QualityGateConfig,
)
from aimake.execution.output_staging import OutputStaging
from aimake.execution.output_validation import OutputValidator
from aimake.execution.runner import BuildRunner
from aimake.graph.dag import Graph
from aimake.hashing.fingerprint import Fingerprinter
from aimake.metrics.quality import QualityGateChecker
from aimake.models import ArtifactStatus


def test_environment_fingerprint_names_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MODEL_NAME", "version-a")
    config = AimakeConfig(
        project=ProjectConfig(name="t", environment_mode="names"),
        environment=["MODEL_NAME"],
        artifacts={"m": ArtifactConfig(type="prompt", source="p.txt")},
    )
    (tmp_path / "p.txt").write_text("x", encoding="utf-8")
    graph = Graph.from_config(config)
    fp1 = Fingerprinter(tmp_path, config, graph).fingerprint("m")

    monkeypatch.setenv("MODEL_NAME", "version-b")
    fp2 = Fingerprinter(tmp_path, config, graph).fingerprint("m")
    assert fp1 == fp2


def test_environment_values_mode_detects_change(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MODEL_NAME", "version-a")
    config = AimakeConfig(
        project=ProjectConfig(name="t", environment_mode="values"),
        environment=["MODEL_NAME"],
        artifacts={"m": ArtifactConfig(type="prompt", source="p.txt")},
    )
    (tmp_path / "p.txt").write_text("x", encoding="utf-8")
    graph = Graph.from_config(config)
    fp1 = Fingerprinter(tmp_path, config, graph).fingerprint("m")

    monkeypatch.setenv("MODEL_NAME", "version-b")
    fp2 = Fingerprinter(tmp_path, config, graph).fingerprint("m")
    assert fp1 != fp2


def test_external_dependency_revision_in_fingerprint(tmp_path: Path) -> None:
    config = AimakeConfig(
        project=ProjectConfig(name="t"),
        artifacts={
            "embed": ArtifactConfig(
                type="generic",
                command="true",
                outputs=["out/"],
                external=[
                    ExternalDependencyConfig(
                        name="api",
                        provider="openai",
                        model="text-embedding-3-small",
                        revision="2024-01",
                    )
                ],
            )
        },
    )
    graph = Graph.from_config(config)
    fp1 = Fingerprinter(tmp_path, config, graph).fingerprint("embed")

    config.artifacts["embed"].external[0].revision = "2024-06"
    graph = Graph.from_config(config)
    fp2 = Fingerprinter(tmp_path, config, graph).fingerprint("embed")
    assert fp1 != fp2


def test_volatile_external_excluded_from_fingerprint(tmp_path: Path) -> None:
    base = ArtifactConfig(
        type="generic",
        command="true",
        outputs=["out/"],
        external=[
            ExternalDependencyConfig(
                name="api",
                provider="openai",
                model="text-embedding-3-small",
                revision="latest",
                volatile=True,
            )
        ],
    )
    config = AimakeConfig(project=ProjectConfig(name="t"), artifacts={"e": base})
    graph = Graph.from_config(config)
    fp1 = Fingerprinter(tmp_path, config, graph).fingerprint("e")

    config.artifacts["e"].external[0].revision = "changed"
    graph = Graph.from_config(config)
    fp2 = Fingerprinter(tmp_path, config, graph).fingerprint("e")
    assert fp1 == fp2


def test_output_validation_catches_empty_file(tmp_path: Path) -> None:
    out = tmp_path / "build" / "eval" / "results.json"
    out.parent.mkdir(parents=True)
    out.write_text("", encoding="utf-8")
    validator = OutputValidator(tmp_path)
    result = validator.validate(
        ["build/eval/results.json"],
        OutputValidationConfig(non_empty=True, min_size_bytes=1),
    )
    assert not result.valid


def test_output_validation_required_keys(tmp_path: Path) -> None:
    out = tmp_path / "results.json"
    out.write_text('{"accuracy": 0.9}', encoding="utf-8")
    validator = OutputValidator(tmp_path)
    result = validator.validate(
        ["results.json"],
        OutputValidationConfig(required_keys=["accuracy", "cost_usd"]),
    )
    assert not result.valid
    assert any("cost_usd" in e for e in result.errors)


def test_atomic_staging_promote(tmp_path: Path) -> None:
    staging = OutputStaging(
        tmp_path, "eval", ["build/eval/out.txt"], enabled=True
    )
    staging.prepare()
    staged = staging._staging_root / "build/eval/out.txt"
    staged.parent.mkdir(parents=True)
    staged.write_text("ok", encoding="utf-8")
    staging.promote()
    final = tmp_path / "build/eval/out.txt"
    assert final.read_text(encoding="utf-8") == "ok"


def test_failed_build_discards_partial_outputs(tmp_path: Path) -> None:
    fail_script = tmp_path / "fail.py"
    fail_script.write_text(
        "import os, sys\n"
        "os.makedirs('build/bad', exist_ok=True)\n"
        "open('build/bad/out.txt','w').write('partial')\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    config = AimakeConfig(
        project=ProjectConfig(name="t", atomic_outputs=True),
        artifacts={
            "bad": ArtifactConfig(
                type="generic",
                command=f"python {fail_script.name}",
                outputs=["build/bad/out.txt"],
            )
        },
    )
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path)
    runner = BuildRunner(tmp_path, config, graph, cache)
    result = runner.build()
    assert not result.success
    assert not (tmp_path / "build/bad/out.txt").exists()
    cache.close()


def test_invalid_output_fails_build(tmp_path: Path) -> None:
    script = tmp_path / "empty_eval.py"
    script.write_text(
        "import os\n"
        "os.makedirs('build/eval', exist_ok=True)\n"
        "open('build/eval/results.json','w').write('{}')\n",
        encoding="utf-8",
    )
    config = AimakeConfig(
        project=ProjectConfig(name="t", atomic_outputs=False),
        artifacts={
            "eval": ArtifactConfig(
                type="evaluation",
                command=f"python {script.name}",
                outputs=["build/eval/results.json"],
                validation=OutputValidationConfig(
                    required_keys=["accuracy"],
                    non_empty=True,
                ),
            )
        },
    )
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path)
    runner = BuildRunner(tmp_path, config, graph, cache)
    result = runner.build()
    assert not result.success
    assert "eval" in result.failed
    cache.close()


def test_plan_includes_cost_estimate(tmp_path: Path) -> None:
    config = AimakeConfig(
        project=ProjectConfig(name="t"),
        artifacts={
            "eval": ArtifactConfig(
                type="generic",
                command="true",
                outputs=["out/"],
                cost_estimate=CostEstimateConfig(cost_usd=1.25, tokens=500),
            )
        },
    )
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path)
    runner = BuildRunner(tmp_path, config, graph, cache)
    plan = runner.plan()
    entry = plan.entries[0]
    assert entry.estimated_cost_usd == 1.25
    assert entry.estimated_tokens == 500
    cache.close()


def test_quality_gate_required_metric() -> None:
    config = AimakeConfig(
        project=ProjectConfig(name="t"),
        artifacts={"x": ArtifactConfig(type="prompt", source="p.txt")},
        quality_gates={"accuracy": QualityGateConfig(minimum=0.9, required=True)},
    )
    checker = QualityGateChecker(config)
    failures = checker.check({})
    assert len(failures) == 1
    assert failures[0].comparison == "required"


def test_revalidation_marks_stale_on_garbage_cache(tmp_path: Path) -> None:
    config = AimakeConfig(
        project=ProjectConfig(name="t"),
        artifacts={
            "eval": ArtifactConfig(
                type="evaluation",
                command="true",
                outputs=["build/eval/results.json"],
                validation=OutputValidationConfig(
                    required_keys=["accuracy", "cost_usd"],
                    revalidate_on_cache_hit=True,
                ),
            )
        },
    )
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path)
    runner = BuildRunner(tmp_path, config, graph, cache)

    out = tmp_path / "build/eval/results.json"
    out.parent.mkdir(parents=True)
    out.write_text("{}", encoding="utf-8")

    fp = runner.compute_fingerprints()["eval"]
    cache.store("eval", fp, outputs=["build/eval/results.json"])

    statuses = runner.compute_statuses()
    assert statuses["eval"] == ArtifactStatus.STALE
    cache.close()
