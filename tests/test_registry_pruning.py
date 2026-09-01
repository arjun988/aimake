"""Tests for artifact registry, hyperband, and multi-fidelity optimization."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aimake.cache.store import Cache
from aimake.config.schema import (
    AimakeConfig,
    ArtifactConfig,
    MetricsConfig,
    ObjectiveConfig,
    OptimizationConfig,
    PruningConfig,
    ProjectConfig,
    RegistryConfig,
    SearchParamConfig,
)
from aimake.experiments.fidelity import apply_fidelity, fidelity_env
from aimake.experiments.hyperband import run_successive_halving
from aimake.experiments.optimizer import Optimizer, TrialResult
from aimake.registry.store import ArtifactRegistry
from aimake.state.database import StateDatabase


def test_registry_register_and_promote(tmp_path: Path) -> None:
    db = StateDatabase(tmp_path / ".aimake")
    reg = ArtifactRegistry(db)

    entry = reg.register("model", "fp-abc", build_id=1, metrics={"accuracy": 0.9})
    assert entry.version == "v1"
    assert entry.stage == "dev"

    promoted = reg.promote("model", "v1", "production")
    assert promoted.stage == "production"

    tagged = reg.tag("model", "v1", ["best", "rag"])
    assert "best" in tagged.tags
    db.close()


def test_registry_list_filter(tmp_path: Path) -> None:
    db = StateDatabase(tmp_path / ".aimake")
    reg = ArtifactRegistry(db)
    reg.register("a", "fp1", stage="dev")
    reg.register("a", "fp2", stage="staging", version="v2")
    assert len(reg.list("a")) == 2
    assert len(reg.list("a", stage="staging")) == 1
    db.close()


def test_apply_fidelity_with_values() -> None:
    pruning = PruningConfig(
        enabled=True,
        min_fidelity=1,
        max_fidelity=3,
        fidelity_param="epochs",
        fidelity_values=[1, 5, 10],
    )
    params = apply_fidelity({"lr": 0.01}, 2, pruning)
    assert params["epochs"] == 5
    env = fidelity_env(2, pruning)
    assert env["AIMAKE_FIDELITY"] == "2"
    assert env["AIMAKE_FIDELITY_VALUE"] == "5"


def test_successive_halving_prunes(tmp_path: Path) -> None:
    pruning = PruningConfig(
        enabled=True,
        strategy="successive_halving",
        min_fidelity=1,
        max_fidelity=2,
        reduction_factor=2,
    )
    configs = [{"x": i} for i in range(4)]
    call_count = 0

    def evaluate(params, level, num):
        nonlocal call_count
        call_count += 1
        value = params["x"] * level
        return TrialResult(
            trial_number=num,
            parameters=params,
            build_id=None,
            metrics={},
            objective_value=float(value),
            success=True,
            fidelity=level,
        )

    result = run_successive_halving(configs, evaluate, pruning, direction="maximize", seed=1)
    assert result.trials
    assert result.best_value is not None
    assert result.pruned_count >= 0


def _pruning_opt_config(tmp_path_command: str) -> AimakeConfig:
    return AimakeConfig(
        project=ProjectConfig(name="opt"),
        registry=RegistryConfig(enabled=True, auto_register=False),
        artifacts={
            "eval": ArtifactConfig(
                type="evaluation",
                command=tmp_path_command,
                outputs=["build/results.json"],
                parameters={"epochs": 1},
                metrics=MetricsConfig(file="build/results.json"),
            ),
        },
        optimization=OptimizationConfig(
            trials=4,
            strategy="hyperband",
            parameter_artifact="eval",
            search_space={
                "scale": SearchParamConfig(type="float", low=1.0, high=2.0, step=1.0),
            },
            objective=ObjectiveConfig(metric="accuracy", direction="maximize", artifact="eval"),
            pruning=PruningConfig(
                enabled=True,
                strategy="successive_halving",
                min_fidelity=1,
                max_fidelity=2,
                fidelity_param="epochs",
                fidelity_values=[1, 3],
            ),
        ),
    )


def test_optimizer_with_pruning(tmp_path: Path) -> None:
    cmd = (
        'python -c "import json, os; from pathlib import Path; '
        "epochs=int(os.environ.get('AIMAKE_FIDELITY_VALUE','1')); "
        "scale=float(os.environ.get('AIMAKE_PARAM_SCALE','1')); "
        "Path('build').mkdir(exist_ok=True); "
        "json.dump({'accuracy': 0.5 + scale*0.1*epochs/3}, open('build/results.json','w'))\""
    )
    config = _pruning_opt_config(cmd)
    cache = Cache(tmp_path / ".aimake", tmp_path, config)
    optimizer = Optimizer(tmp_path, config, cache)
    result = optimizer.run(trials=2)
    assert result.trials
    assert any(t.fidelity is not None for t in result.trials)
    cache.close()


def test_optuna_multifidelity_mock(tmp_path: Path) -> None:
    pytest.importorskip("optuna")
    cmd = (
        'python -c "import json, os; from pathlib import Path; '
        "val=float(os.environ.get('AIMAKE_FIDELITY_VALUE','1')); "
        "Path('build').mkdir(exist_ok=True); "
        "json.dump({'accuracy': 0.4 + val*0.1}, open('build/results.json','w'))\""
    )
    config = _pruning_opt_config(cmd)
    config.optimization.strategy = "optuna"  # type: ignore[union-attr]
    config.optimization.pruning.strategy = "hyperband"  # type: ignore[union-attr]
    cache = Cache(tmp_path / ".aimake", tmp_path, config)
    optimizer = Optimizer(tmp_path, config, cache)
    result = optimizer.run(trials=2)
    assert len(result.trials) >= 2
    cache.close()


def test_registry_auto_register_on_build(tmp_path: Path) -> None:
    from aimake.execution.runner import BuildRunner
    from aimake.graph.dag import Graph

    config = AimakeConfig(
        project=ProjectConfig(name="t"),
        registry=RegistryConfig(enabled=True, auto_register=True),
        artifacts={
            "out": ArtifactConfig(
                type="generic",
                command='python -c "from pathlib import Path; Path(\'build\').mkdir(exist_ok=True); open(\'build/o.txt\',\'w\').write(\'x\')"',
                outputs=["build/o.txt"],
            ),
        },
    )
    graph = Graph.from_config(config)
    cache = Cache(tmp_path / ".aimake", tmp_path, config)
    runner = BuildRunner(tmp_path, config, graph, cache)
    runner.build()
    entries = ArtifactRegistry(cache.state_db).list("out")
    assert len(entries) == 1
    assert entries[0].version == "v1"
    cache.close()
