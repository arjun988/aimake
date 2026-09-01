"""Hyperband and successive-halving schedulers."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable

from aimake.config.schema import PruningConfig
from aimake.experiments.fidelity import apply_fidelity, fidelity_steps


@dataclass
class HalvingResult:
    """Outcome of a halving / hyperband run."""

    trials: list[Any] = field(default_factory=list)
    pruned_count: int = 0
    best_trial: Any | None = None
    best_value: float | None = None


EvaluateFn = Callable[[dict[str, Any], int, int], Any]


def run_successive_halving(
    configs: list[dict[str, Any]],
    evaluate: EvaluateFn,
    pruning: PruningConfig,
    *,
    direction: str = "maximize",
    seed: int | None = None,
) -> HalvingResult:
    """Run successive halving across fidelity levels."""
    rng = random.Random(seed)
    active = list(configs)
    rng.shuffle(active)
    result = HalvingResult()
    best_value: float | None = None
    best_trial = None
    steps = fidelity_steps(pruning)
    eta = pruning.reduction_factor

    for step_idx, level in enumerate(steps):
        step_trials: list[Any] = []
        for trial_num, params in enumerate(active, start=1):
            trial = evaluate(params, level, trial_num)
            step_trials.append(trial)
            result.trials.append(trial)
            if getattr(trial, "pruned", False):
                result.pruned_count += 1
                continue
            value = getattr(trial, "objective_value", None)
            if value is not None:
                if best_value is None or _is_better(value, best_value, direction):
                    best_value = value
                    best_trial = trial

        if step_idx == len(steps) - 1:
            break

        successful = [
            (t, t.parameters if hasattr(t, "parameters") else {})
            for t in step_trials
            if not getattr(t, "pruned", False)
            and getattr(t, "objective_value", None) is not None
        ]
        if not successful:
            break

        successful.sort(
            key=lambda x: x[0].objective_value,
            reverse=(direction == "maximize"),
        )
        keep = max(1, math.ceil(len(successful) / eta))
        pruned_configs = {id(p) for _, p in successful[keep:]}
        for t, p in successful[keep:]:
            t.pruned = True  # type: ignore[attr-defined]
            result.pruned_count += 1
        active = [p for t, p in successful[:keep]]

    result.best_trial = best_trial
    result.best_value = best_value
    return result


def run_hyperband(
    configs: list[dict[str, Any]],
    evaluate: EvaluateFn,
    pruning: PruningConfig,
    *,
    direction: str = "maximize",
    seed: int | None = None,
) -> HalvingResult:
    """Run Hyperband brackets over trial configurations."""
    rng = random.Random(seed)
    eta = pruning.reduction_factor
    max_fidelity = pruning.max_fidelity
    s_max = int(math.floor(math.log(max_fidelity, eta))) if max_fidelity > 1 else 0

    all_trials: list[Any] = []
    pruned_count = 0
    best_value: float | None = None
    best_trial = None

    for s in range(s_max, -1, -1):
        n = max(1, math.ceil(len(configs) / (s_max + 1) * (eta ** s)))
        bracket_configs = rng.sample(configs, min(n, len(configs)))
        r = max(1, int(max_fidelity * (eta ** -s)))
        levels = [lvl for lvl in fidelity_steps(pruning) if lvl >= r] or [pruning.min_fidelity]

        active = list(bracket_configs)
        for level in levels:
            step_trials: list[Any] = []
            for params in active:
                trial = evaluate(params, level, len(all_trials) + 1)
                step_trials.append(trial)
                all_trials.append(trial)
                value = getattr(trial, "objective_value", None)
                if value is not None and (
                    best_value is None or _is_better(value, best_value, direction)
                ):
                    best_value = value
                    best_trial = trial

            if level == levels[-1]:
                break

            successful = [
                (t, t.parameters)
                for t in step_trials
                if getattr(t, "objective_value", None) is not None
            ]
            if not successful:
                break
            successful.sort(
                key=lambda x: x[0].objective_value,
                reverse=(direction == "maximize"),
            )
            keep = max(1, math.ceil(len(successful) / eta))
            for t, _ in successful[keep:]:
                t.pruned = True  # type: ignore[attr-defined]
                pruned_count += 1
            active = [p for _, p in successful[:keep]]

    return HalvingResult(
        trials=all_trials,
        pruned_count=pruned_count,
        best_trial=best_trial,
        best_value=best_value,
    )


def _is_better(value: float, best: float, direction: str) -> bool:
    if direction == "maximize":
        return value > best
    return value < best
