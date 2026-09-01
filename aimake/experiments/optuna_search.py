"""Optuna-backed Bayesian search with multi-fidelity pruners."""

from __future__ import annotations

from typing import Any

from aimake.config.schema import ObjectiveConfig, PruningConfig, SearchParamConfig


def require_optuna():
    try:
        import optuna
    except ImportError as e:
        raise ImportError(
            "Bayesian/Optuna optimization requires optuna. Install with: pip install aimake[optuna]"
        ) from e
    return optuna


def create_pruner(pruning: PruningConfig | None):
    """Create an Optuna pruner from aimake pruning config."""
    if pruning is None or not pruning.enabled:
        return None
    optuna = require_optuna()
    if pruning.strategy == "successive_halving":
        return optuna.pruners.SuccessiveHalvingPruner(
            min_resource=pruning.min_fidelity,
            reduction_factor=pruning.reduction_factor,
        )
    return optuna.pruners.HyperbandPruner(
        min_resource=pruning.min_fidelity,
        max_resource=pruning.max_fidelity,
        reduction_factor=pruning.reduction_factor,
    )


def create_study(
    objective: ObjectiveConfig,
    *,
    strategy: str,
    seed: int | None = None,
    pruning: PruningConfig | None = None,
):
    """Create an Optuna study for single- or multi-objective search."""
    optuna = require_optuna()
    from optuna.samplers import TPESampler

    directions = list(objective.metric_directions().values())
    metric_names = objective.metric_names()
    pruner = create_pruner(pruning)

    sampler = TPESampler(seed=seed)
    if len(metric_names) > 1:
        return optuna.create_study(directions=directions, sampler=sampler, pruner=pruner)

    return optuna.create_study(direction=directions[0], sampler=sampler, pruner=pruner)


def suggest_parameters(
    trial: Any,
    search_space: dict[str, SearchParamConfig],
) -> dict[str, Any]:
    """Suggest parameters for one Optuna trial."""
    params: dict[str, Any] = {}
    for name, spec in search_space.items():
        if spec.type == "categorical":
            params[name] = trial.suggest_categorical(name, list(spec.choices or []))
        elif spec.type == "int":
            step = int(spec.step or 1)
            params[name] = trial.suggest_int(
                name,
                int(spec.low),
                int(spec.high),
                step=step,
            )
        else:
            params[name] = trial.suggest_float(
                name,
                float(spec.low),
                float(spec.high),
                step=spec.step,
            )
    return params


def preview_trials(
    objective: ObjectiveConfig,
    search_space: dict[str, SearchParamConfig],
    *,
    strategy: str,
    max_trials: int,
    seed: int | None = None,
    pruning: PruningConfig | None = None,
) -> list[dict[str, Any]]:
    """Generate parameter sets via Optuna ask without running builds."""
    study = create_study(objective, strategy=strategy, seed=seed, pruning=pruning)
    trials: list[dict[str, Any]] = []
    for _ in range(max_trials):
        trial = study.ask()
        params = suggest_parameters(trial, search_space)
        trials.append(params)
        values = [0.0] * len(objective.metric_names())
        if len(values) > 1:
            study.tell(trial, values)
        else:
            study.tell(trial, values[0])
    return trials
