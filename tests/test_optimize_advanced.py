"""Tests for Pareto front, early stopping, Optuna, and MLflow export."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aimake.cache.store import Cache
from aimake.config.schema import (
    AimakeConfig,
    ArtifactConfig,
    EarlyStoppingConfig,
    MetricsConfig,
    MLflowConfig,
    ObjectiveConfig,
    OptimizationConfig,
    ProjectConfig,
    SearchParamConfig,
)
from aimake.experiments.mlflow_export import export_optimization
from aimake.experiments.optimizer import OptimizationResult, Optimizer, TrialResult
from aimake.experiments.pareto import dominates, pareto_front_indices
from aimake.graph.dag import Graph


def test_dominates_maximize() -> None:
    directions = {"accuracy": "maximize", "latency_ms": "minimize"}
    a = {"accuracy": 0.9, "latency_ms": 100}
    b = {"accuracy": 0.8, "latency_ms": 150}
    assert dominates(a, b, directions)
    assert not dominates(b, a, directions)


def test_pareto_front_indices() -> None:
    rows = [
        {"accuracy": 0.9, "cost": 2.0},
        {"accuracy": 0.85, "cost": 1.0},
        {"accuracy": 0.8, "cost": 3.0},
    ]
    directions = {"accuracy": "maximize", "cost": "minimize"}
    front = pareto_front_indices(rows, directions)
    assert 0 in front
    assert 1 in front
    assert 2 not in front


def _opt_config(**overrides) -> AimakeConfig:
    opt_kwargs: dict = {
        "trials": 4,
        "strategy": "grid",
        "parameter_artifact": "eval",
        "search_space": {
            "scale": SearchParamConfig(type="float", low=1.0, high=2.0, step=1.0),
        },
        "objective": ObjectiveConfig(metric="accuracy", direction="maximize", artifact="eval"),
    }
    opt_kwargs.update(overrides)
    optimization = OptimizationConfig(**opt_kwargs)
    return AimakeConfig(
        project=ProjectConfig(name="opt-test"),
        artifacts={
            "eval": ArtifactConfig(
                type="evaluation",
                command=(
                    'python -c "import json, os; from pathlib import Path; '
                    "scale=float(os.environ.get('AIMAKE_PARAM_SCALE','1')); "
                    "Path('build').mkdir(exist_ok=True); "
                    "json.dump({'accuracy': 0.5 + scale * 0.1, 'cost': 3-scale}, open('build/results.json','w'))\""
                ),
                outputs=["build/results.json"],
                parameters={"scale": 1.0},
                metrics=MetricsConfig(file="build/results.json"),
            ),
        },
        optimization=optimization,
    )


def test_early_stopping(tmp_path: Path) -> None:
    config = AimakeConfig(
        project=ProjectConfig(name="opt-test"),
        artifacts={
            "eval": ArtifactConfig(
                type="evaluation",
                command=(
                    'python -c "import json; from pathlib import Path; '
                    "Path('build').mkdir(exist_ok=True); "
                    "json.dump({'accuracy': 0.65}, open('build/results.json','w'))\""
                ),
                outputs=["build/results.json"],
                parameters={"scale": 1.0},
                metrics=MetricsConfig(file="build/results.json"),
            ),
        },
        optimization=OptimizationConfig(
            trials=5,
            strategy="grid",
            parameter_artifact="eval",
            search_space={
                "scale": SearchParamConfig(type="float", low=1.0, high=3.0, step=1.0),
            },
            objective=ObjectiveConfig(metric="accuracy", direction="maximize", artifact="eval"),
            early_stopping=EarlyStoppingConfig(enabled=True, patience=1, min_trials=1),
        ),
    )
    cache = Cache(tmp_path / ".aimake", tmp_path, config)
    optimizer = Optimizer(tmp_path, config, cache)
    result = optimizer.run()
    assert result.stopped_early
    assert len(result.trials) == 2
    cache.close()


def test_multi_objective_pareto(tmp_path: Path) -> None:
    config = _opt_config(
        objective=ObjectiveConfig(
            metrics=["accuracy", "cost"],
            directions=["maximize", "minimize"],
            artifact="eval",
        ),
    )
    cache = Cache(tmp_path / ".aimake", tmp_path, config)
    optimizer = Optimizer(tmp_path, config, cache)
    result = optimizer.run()
    assert result.pareto_front
    assert len(result.pareto_front) >= 1
    cache.close()


def test_optuna_strategy(tmp_path: Path) -> None:
    pytest.importorskip("optuna")
    config = _opt_config(strategy="bayesian", trials=2)
    cache = Cache(tmp_path / ".aimake", tmp_path, config)
    optimizer = Optimizer(tmp_path, config, cache)
    result = optimizer.run(trials=2)
    assert len(result.trials) == 2
    assert result.success
    cache.close()


def test_mlflow_export_mock() -> None:
    trial = TrialResult(
        trial_number=1,
        parameters={"scale": 1.5},
        build_id=1,
        metrics={"accuracy": 0.65},
        objective_value=0.65,
        success=True,
    )
    result = OptimizationResult(
        experiment_id=1,
        trials=[trial],
        best_trial=trial,
        best_value=0.65,
        best_build_id=1,
        best_parameters={"scale": 1.5},
    )

    mock_mlflow = MagicMock()
    mock_parent = MagicMock()
    mock_parent.info.run_id = "run-123"
    mock_mlflow.start_run.return_value.__enter__.return_value = mock_parent

    with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
        run_id = export_optimization(
            config=MLflowConfig(enabled=True, experiment_name="test-exp"),
            experiment_name="test-exp",
            strategy="grid",
            result=result,
            objective_names=["accuracy"],
            objective_directions={"accuracy": "maximize"},
        )

    assert run_id == "run-123"
    mock_mlflow.set_experiment.assert_called_once()
