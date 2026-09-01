"""Test incremental build semantics."""

from pathlib import Path

from aimake.cache.store import Cache
from aimake.config.schema import AimakeConfig, ArtifactConfig, ProjectConfig
from aimake.execution.runner import BuildRunner
from aimake.graph.dag import Graph
from aimake.graph.planner import Planner
from aimake.hashing.fingerprint import Fingerprinter
from aimake.models import ArtifactStatus


def _rag_like_config() -> AimakeConfig:
    return AimakeConfig(
        project=ProjectConfig(name="test"),
        artifacts={
            "dataset": ArtifactConfig(type="dataset", source="data/train.jsonl"),
            "preprocess": ArtifactConfig(
                type="dataset",
                depends_on=["dataset"],
                command="python scripts/preprocess.py",
                outputs=["build/processed/out.txt"],
            ),
            "embedding": ArtifactConfig(
                type="embedding",
                depends_on=["preprocess"],
                command="python scripts/embed.py",
                outputs=["build/embedding/out.txt"],
            ),
            "index": ArtifactConfig(
                type="vector_index",
                depends_on=["embedding"],
                command="python scripts/index.py",
                outputs=["build/index/out.txt"],
            ),
            "prompt": ArtifactConfig(type="prompt", source="prompts/system.txt"),
            "evaluation": ArtifactConfig(
                type="evaluation",
                depends_on=["index", "prompt"],
                command="python scripts/eval.py",
                outputs=["build/evaluation/out.txt"],
            ),
            "report": ArtifactConfig(
                type="report",
                depends_on=["evaluation"],
                command="python scripts/report.py",
                outputs=["build/report/out.txt"],
            ),
        },
    )


def _setup_project(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "train.jsonl").write_text('{"text": "hello"}\n')
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "system.txt").write_text("You are helpful.")
    (tmp_path / "scripts").mkdir()

    for script, content in {
        "preprocess.py": "import os; os.makedirs('build/processed', exist_ok=True); open('build/processed/out.txt','w').write('p')",
        "embed.py": "import os; os.makedirs('build/embedding', exist_ok=True); open('build/embedding/out.txt','w').write('e')",
        "index.py": "import os; os.makedirs('build/index', exist_ok=True); open('build/index/out.txt','w').write('i')",
        "eval.py": "import os; os.makedirs('build/evaluation', exist_ok=True); open('build/evaluation/out.txt','w').write('v')",
        "report.py": "import os; os.makedirs('build/report', exist_ok=True); open('build/report/out.txt','w').write('r')",
    }.items():
        (tmp_path / "scripts" / script).write_text(content)


def test_full_pipeline_first_build(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    config = _rag_like_config()
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path)
    runner = BuildRunner(tmp_path, config, graph, cache)

    result = runner.build()
    assert result.success
    assert len(result.rebuilt) == 7
    cache.close()


def test_second_build_all_cached(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    config = _rag_like_config()
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path)

    runner = BuildRunner(tmp_path, config, graph, cache)
    runner.build()

    runner2 = BuildRunner(tmp_path, config, graph, cache)
    result = runner2.build()
    assert result.success
    assert len(result.rebuilt) == 0
    assert len(result.reused) == 7
    cache.close()


def test_prompt_change_invalidates_downstream(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    config = _rag_like_config()
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path)

    runner = BuildRunner(tmp_path, config, graph, cache)
    runner.build()

    # Modify prompt
    (tmp_path / "prompts" / "system.txt").write_text("Changed prompt content.")

    runner2 = BuildRunner(tmp_path, config, graph, cache)
    runner2.compute_fingerprints()
    statuses = runner2.compute_statuses()
    plan = runner2.plan()

    assert statuses["dataset"] == ArtifactStatus.UP_TO_DATE
    assert statuses["preprocess"] == ArtifactStatus.UP_TO_DATE
    assert statuses["embedding"] == ArtifactStatus.UP_TO_DATE
    assert statuses["index"] == ArtifactStatus.UP_TO_DATE
    assert statuses["prompt"] in (ArtifactStatus.CHANGED, ArtifactStatus.STALE)
    assert statuses["evaluation"] == ArtifactStatus.STALE
    assert statuses["report"] == ArtifactStatus.STALE

    to_run = set(plan.to_run)
    assert "prompt" in to_run or "evaluation" in to_run
    assert "evaluation" in to_run
    assert "report" in to_run
    assert "dataset" not in to_run
    assert "embedding" not in to_run

    cache.close()


def test_dataset_change_rebuilds_upstream_not_prompt(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    config = _rag_like_config()
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path)

    runner = BuildRunner(tmp_path, config, graph, cache)
    runner.build()

    (tmp_path / "data" / "train.jsonl").write_text('{"text": "new data"}\n')

    runner2 = BuildRunner(tmp_path, config, graph, cache)
    runner2.compute_fingerprints()
    statuses = runner2.compute_statuses()
    plan = runner2.plan()

    to_run = set(plan.to_run)
    assert "dataset" in to_run or statuses["dataset"] != ArtifactStatus.UP_TO_DATE
    assert "preprocess" in to_run
    assert "embedding" in to_run
    assert "index" in to_run
    assert "evaluation" in to_run
    assert "report" in to_run
    # Prompt should remain cached
    assert "prompt" not in to_run

    cache.close()


def test_explain_report(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    config = _rag_like_config()
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path)

    runner = BuildRunner(tmp_path, config, graph, cache)
    runner.build()

    (tmp_path / "prompts" / "system.txt").write_text("New prompt.")
    runner2 = BuildRunner(tmp_path, config, graph, cache)
    explanation = runner2.explain("report")

    assert explanation.target == "report"
    assert explanation.conclusion
    assert "rebuilt" in explanation.conclusion.lower()

    cache.close()
