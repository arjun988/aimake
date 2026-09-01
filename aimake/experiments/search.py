"""Search space sampling for hyperparameter optimization."""

from __future__ import annotations

import itertools
import random
from typing import Any

from aimake.config.schema import SearchParamConfig


def _grid_values(param: SearchParamConfig) -> list[Any]:
    if param.type == "categorical":
        return list(param.choices or [])

    assert param.low is not None and param.high is not None
    if param.type == "int":
        step = int(param.step or 1)
        low = int(param.low)
        high = int(param.high)
        return list(range(low, high + 1, step))

    step = param.step or (param.high - param.low) / 4.0
    values: list[float] = []
    current = float(param.low)
    while current <= float(param.high) + 1e-9:
        values.append(round(current, 6))
        current += step
    return values


def _random_value(param: SearchParamConfig, rng: random.Random) -> Any:
    if param.type == "categorical":
        return rng.choice(list(param.choices or []))
    assert param.low is not None and param.high is not None
    if param.type == "int":
        return rng.randint(int(param.low), int(param.high))
    return round(rng.uniform(float(param.low), float(param.high)), 6)


def generate_trials(
    search_space: dict[str, SearchParamConfig],
    *,
    strategy: str,
    max_trials: int,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """Generate trial parameter sets from a search space."""
    if not search_space:
        return []

    if strategy == "grid":
        names = sorted(search_space.keys())
        value_lists = [_grid_values(search_space[name]) for name in names]
        combos = [
            dict(zip(names, values, strict=True))
            for values in itertools.product(*value_lists)
        ]
        return combos[:max_trials]

    rng = random.Random(seed)
    trials: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    attempts = 0
    while len(trials) < max_trials and attempts < max_trials * 20:
        attempts += 1
        sample = {name: _random_value(spec, rng) for name, spec in search_space.items()}
        key = tuple(sorted((k, repr(v)) for k, v in sample.items()))
        if key in seen:
            continue
        seen.add(key)
        trials.append(sample)
    return trials
