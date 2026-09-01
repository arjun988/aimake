"""Tests for hyperparameter search and optimization."""

from pathlib import Path

from aimake.cache.store import Cache
from aimake.config.schema import (
    AimakeConfig,
    ArtifactConfig,
    MetricsConfig,
    ObjectiveConfig,
    OptimizationConfig,
    ProjectConfig,
    SearchParamConfig,
)
from aimake.experiments.optimizer import Optimizer
from aimake.experiments.search import generate_trials
from aimake.graph.dag import Graph


def test_generate_grid_trials() -> None:
    space = {
        "a": SearchParamConfig(type="float", low=0.0, high=1.0, step=0.5),
        "b": SearchParamConfig(type="int", low=1, high=2, step=1),
    }
    trials = generate_trials(space, strategy="grid", max_trials=10)
    assert len(trials) == 6
    assert {"a": 0.0, "b": 1} in trials


def test_generate_random_trials() -> None:
    space = {
        "x": SearchParamConfig(type="float", low=0.0, high=1.0),
    }
    trials = generate_trials(space, strategy="random", max_trials=3, seed=42)
    assert len(trials) == 3
    assert all(0.0 <= t["x"] <= 1.0 for t in trials)


def _opt_config() -> AimakeConfig:
    return AimakeConfig(
        project=ProjectConfig(name="opt-test"),
        artifacts={
            "eval": ArtifactConfig(
                type="evaluation",
                command=(
                    'python -c "import json, os; from pathlib import Path; '
                    "scale=float(os.environ.get('AIMAKE_PARAM_SCALE','1')); "
                    "Path('build').mkdir(exist_ok=True); "
                    "json.dump({'accuracy': 0.5 + scale * 0.1}, open('build/results.json','w'))\""
                ),
                outputs=["build/results.json"],
                parameters={"scale": 1.0},
                metrics=MetricsConfig(file="build/results.json"),
            ),
        },
        optimization=OptimizationConfig(
            trials=2,
            strategy="grid",
            parameter_artifact="eval",
            search_space={
                "scale": SearchParamConfig(type="float", low=1.0, high=2.0, step=1.0),
            },
            objective=ObjectiveConfig(metric="accuracy", direction="maximize", artifact="eval"),
        ),
    )


def test_optimize_end_to_end(tmp_path: Path) -> None:
    config = _opt_config()
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path, config)

    optimizer = Optimizer(tmp_path, config, cache)
    result = optimizer.run()

    assert result.success
    assert len(result.trials) == 2
    assert result.best_value == 0.7
    assert result.best_parameters["scale"] == 2.0

    experiments = cache.state_db.get_experiments()
    assert len(experiments) == 1
    trials = cache.state_db.get_experiment_trials(experiments[0]["id"])
    assert len(trials) == 2
    cache.close()


def test_optimize_dry_run(tmp_path: Path) -> None:
    config = _opt_config()
    cache = Cache(tmp_path / ".aimake", tmp_path, config)
    optimizer = Optimizer(tmp_path, config, cache)
    result = optimizer.run(dry_run=True)
    assert len(result.trials) == 2
    assert result.trials[0].build_id is None
    cache.close()


def test_parameter_env_injected(tmp_path: Path) -> None:
    from aimake.execution.runner import BuildRunner

    config = _opt_config()
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path, config)
    runner = BuildRunner(tmp_path, config, graph, cache)
    result = runner.build(
        targets=["eval"],
        force={"eval"},
        build_parameters={"scale": 2.0},
    )
    assert result.success
    data = (tmp_path / "build" / "results.json").read_text(encoding="utf-8")
    assert "0.7" in data
    cache.close()
