"""Optuna-backed Bayesian search."""

from __future__ import annotations

from typing import Any

from aimake.config.schema import ObjectiveConfig, SearchParamConfig


def require_optuna():
    try:
        import optuna
    except ImportError as e:
        raise ImportError(
            "Bayesian/Optuna optimization requires optuna. Install with: pip install aimake[optuna]"
        ) from e
    return optuna


def create_study(
    objective: ObjectiveConfig,
    *,
    strategy: str,
    seed: int | None = None,
):
    """Create an Optuna study for single- or multi-objective search."""
    optuna = require_optuna()
    from optuna.samplers import TPESampler

    directions = list(objective.metric_directions().values())
    metric_names = objective.metric_names()

    sampler = TPESampler(seed=seed)
    if len(metric_names) > 1:
        return optuna.create_study(directions=directions, sampler=sampler)

    return optuna.create_study(direction=directions[0], sampler=sampler)


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
) -> list[dict[str, Any]]:
    """Generate parameter sets via Optuna ask without running builds."""
    study = create_study(objective, strategy=strategy, seed=seed)
    trials: list[dict[str, Any]] = []
    for _ in range(max_trials):
        trial = study.ask()
        params = suggest_parameters(trial, search_space)
        trials.append(params)
        # Placeholder values for dry-run tell
        values = [0.0] * len(objective.metric_names())
        study.tell(trial, *values) if len(values) > 1 else study.tell(trial, values[0])
    return trials
