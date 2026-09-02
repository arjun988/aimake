"""Tests for trust features: restore, validation.command, attest, repro, lineage."""

from __future__ import annotations

from pathlib import Path

import pytest

from aimake.cache.store import Cache
from aimake.config.schema import (
    AimakeConfig,
    ArtifactConfig,
    AttestationConfig,
    ExternalDependencyConfig,
    LineageConfig,
    OutputValidationConfig,
    ProjectConfig,
)
from aimake.execution.output_validation import OutputValidator
from aimake.execution.runner import BuildRunner
from aimake.graph.dag import Graph
from aimake.models import ArtifactStatus, BuildAction
from aimake.project import Project


def test_missing_outputs_restore_from_cache(tmp_path: Path) -> None:
    """#23 — when outputs are deleted but cache blobs exist, plan RESTORE."""
    config = AimakeConfig(
        project=ProjectConfig(name="test"),
        artifacts={
            "a": ArtifactConfig(
                type="generic",
                command=(
                    "python -c \"import os; os.makedirs('build/a', exist_ok=True); "
                    "open('build/a/o.txt','w').write('a')\""
                ),
                outputs=["build/a/o.txt"],
            ),
        },
    )
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path, config)
    runner = BuildRunner(tmp_path, config, graph, cache)
    result = runner.build()
    assert result.success

    import shutil

    shutil.rmtree(tmp_path / "build")

    runner2 = BuildRunner(tmp_path, config, graph, cache)
    statuses = runner2.compute_statuses()
    assert statuses["a"] == ArtifactStatus.CACHED
    plan = runner2.plan()
    assert plan.entries[0].action == BuildAction.RESTORE

    result2 = runner2.build()
    assert result2.success
    assert "a" in result2.reused
    assert (tmp_path / "build" / "a" / "o.txt").is_file()
    cache.close()


def test_validation_command(tmp_path: Path) -> None:
    (tmp_path / "out.txt").write_text("ok", encoding="utf-8")
    (tmp_path / "check.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        "sys.exit(0 if Path('out.txt').read_text().strip()=='ok' else 1)\n",
        encoding="utf-8",
    )
    v = OutputValidator(tmp_path)
    ok = v.validate(
        ["out.txt"],
        OutputValidationConfig(command="python check.py"),
    )
    assert ok.valid

    (tmp_path / "out.txt").write_text("bad", encoding="utf-8")
    bad = v.validate(
        ["out.txt"],
        OutputValidationConfig(command="python check.py"),
    )
    assert not bad.valid
    assert any("validation.command" in e for e in bad.errors)


def test_attestation_written(tmp_path: Path) -> None:
    (tmp_path / "aimake.yaml").write_text(
        """
project:
  name: att
attestation:
  enabled: true
artifacts:
  data:
    type: dataset
    source: data.txt
""",
        encoding="utf-8",
    )
    (tmp_path / "data.txt").write_text("x", encoding="utf-8")
    project = Project.load(tmp_path / "aimake.yaml")
    result = project.build()
    assert result.success
    latest = tmp_path / ".aimake" / "attestations" / "data" / "latest.json"
    assert latest.is_file()
    text = latest.read_text(encoding="utf-8")
    assert "slsa.dev/provenance" in text
    project.close()


def test_repro_and_lineage(tmp_path: Path) -> None:
    (tmp_path / "aimake.yaml").write_text(
        """
project:
  name: repro
lineage:
  enabled: true
  formats: [openlineage, mlflow]
artifacts:
  data:
    type: dataset
    source: data.txt
""",
        encoding="utf-8",
    )
    (tmp_path / "data.txt").write_text("x", encoding="utf-8")
    project = Project.load(tmp_path / "aimake.yaml")
    project.build()
    md = project.repro_report(fmt="markdown")
    assert md.is_file()
    assert "reproducibility" in md.read_text(encoding="utf-8").lower()
    written = project.export_lineage()
    assert "openlineage" in written
    assert written["openlineage"].is_file()
    graph = project.lineage_graph()
    assert len(graph["nodes"]) == 1
    project.close()


def test_external_probe_mode_schema() -> None:
    dep = ExternalDependencyConfig(
        name="llm",
        provider="openai",
        model="gpt-4o",
        revision="1",
        probe=True,
        probe_mode="invalidate",
    )
    assert dep.probe_mode == "invalidate"
    with pytest.raises(Exception):
        ExternalDependencyConfig(name="x", probe_mode="nope")
