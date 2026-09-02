"""Tests for init --from generators and new CLI features."""

from pathlib import Path

import pytest

from aimake.init.generators import generate_from, supported_sources
from aimake.project import Project


def test_supported_sources() -> None:
    assert "makefile" in supported_sources()
    assert "dvc" in supported_sources()


def test_from_makefile(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text(
        "prepare:\n\tpython -c \"print(1)\"\n\n"
        "train: prepare\n\tpython -c \"print(2)\"\n",
        encoding="utf-8",
    )
    yaml_text = generate_from("makefile", tmp_path, "demo")
    assert "prepare" in yaml_text
    assert "train" in yaml_text
    assert "depends_on" in yaml_text


def test_from_dvc_yaml(tmp_path: Path) -> None:
    (tmp_path / "dvc.yaml").write_text(
        """
stages:
  prepare:
    cmd: python prep.py
    deps:
      - data/raw
    outs:
      - data/processed
  train:
    cmd: python train.py
    deps:
      - data/processed
    outs:
      - models/model.pkl
""",
        encoding="utf-8",
    )
    yaml_text = generate_from("dvc", tmp_path, "demo")
    assert "prepare" in yaml_text
    assert "train" in yaml_text
    assert "python prep.py" in yaml_text


def test_from_prefect(tmp_path: Path) -> None:
    (tmp_path / "flows.py").write_text(
        "from prefect import flow\n\n"
        "@flow\n"
        "def my_pipeline():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    yaml_text = generate_from("prefect", tmp_path, "demo")
    assert "my_pipeline" in yaml_text or "flows_my_pipeline" in yaml_text


def test_from_airflow(tmp_path: Path) -> None:
    (tmp_path / "dag.py").write_text(
        "from airflow import DAG\n"
        "from airflow.operators.python import PythonOperator\n"
        "with DAG(dag_id='demo_dag') as dag:\n"
        "    PythonOperator(task_id='extract', python_callable=lambda: None)\n",
        encoding="utf-8",
    )
    yaml_text = generate_from("airflow-dag", tmp_path, "demo")
    assert "demo_dag" in yaml_text
    assert "extract" in yaml_text


def test_project_init_from_makefile(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text(
        "run:\n\tpython -c \"open('out.txt','w').write('x')\"\n",
        encoding="utf-8",
    )
    config_path = Project.init(tmp_path, from_source="makefile")
    assert config_path.is_file()
    assert "run" in config_path.read_text(encoding="utf-8")


def test_explain_tree(tmp_path: Path) -> None:
    from aimake.config.schema import AimakeConfig, ArtifactConfig, ProjectConfig
    from aimake.execution.runner import BuildRunner
    from aimake.graph.dag import Graph
    from aimake.cache.store import Cache

    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    config = AimakeConfig(
        project=ProjectConfig(name="t"),
        artifacts={
            "a": ArtifactConfig(type="prompt", source="a.txt"),
            "b": ArtifactConfig(
                type="generic",
                command="python -c \"import os; os.makedirs('build/b', exist_ok=True); open('build/b/o','w').write('b')\"",
                outputs=["build/b/o"],
                depends_on=["a"],
            ),
        },
    )
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path)
    runner = BuildRunner(tmp_path, config, graph, cache)
    runner.build()
    (tmp_path / "a.txt").write_text("changed", encoding="utf-8")
    runner2 = BuildRunner(tmp_path, config, graph, cache)
    result = runner2.explain("b", tree=True)
    assert result.tree
    assert any(n.name == "a" for n in result.tree)
    cache.close()


def test_plan_json_format(tmp_path: Path) -> None:
    from aimake.config.schema import AimakeConfig, ArtifactConfig, ProjectConfig
    from aimake.execution.runner import BuildRunner
    from aimake.graph.dag import Graph
    from aimake.cache.store import Cache
    import json

    config = AimakeConfig(
        project=ProjectConfig(name="t"),
        artifacts={
            "x": ArtifactConfig(
                type="generic",
                command="python -c \"open('o','w').write('x')\"",
                outputs=["o"],
            )
        },
    )
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path)
    runner = BuildRunner(tmp_path, config, graph, cache)
    plan = runner.plan()
    payload = {
        "to_run": plan.to_run,
        "estimated_total_cost_usd": plan.estimated_total_cost_usd,
    }
    json.dumps(payload)
    cache.close()


def test_collect_watch_paths(tmp_path: Path) -> None:
    from aimake.config.schema import AimakeConfig, ArtifactConfig, ProjectConfig
    from aimake.watch import collect_watch_paths

    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "p.txt").write_text("hi", encoding="utf-8")
    config = AimakeConfig(
        project=ProjectConfig(name="t"),
        artifacts={"p": ArtifactConfig(type="prompt", source="prompts/p.txt")},
    )
    paths = collect_watch_paths(tmp_path, config)
    assert any("p.txt" in str(p) for p in paths)
