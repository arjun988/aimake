"""Multi-fidelity parameter scaling for optimization."""

from __future__ import annotations

from typing import Any

from aimake.config.schema import PruningConfig, SearchParamConfig


def fidelity_steps(pruning: PruningConfig) -> list[int]:
    """Return ordered fidelity levels (e.g. [1, 2, 3])."""
    return list(range(pruning.min_fidelity, pruning.max_fidelity + 1))


def fidelity_param_value(level: int, pruning: PruningConfig) -> float | int:
    """Resolve the search-parameter value for a fidelity level."""
    if pruning.fidelity_values:
        idx = level - pruning.min_fidelity
        if idx < 0 or idx >= len(pruning.fidelity_values):
            raise ValueError(
                f"Fidelity level {level} has no entry in fidelity_values "
                f"(need {pruning.max_fidelity - pruning.min_fidelity + 1} values)"
            )
        return pruning.fidelity_values[idx]
    return level


def apply_fidelity(
    params: dict[str, Any],
    level: int,
    pruning: PruningConfig,
    search_space: dict[str, SearchParamConfig] | None = None,
) -> dict[str, Any]:
    """Merge base trial params with fidelity-scaled values."""
    merged = dict(params)
    if not pruning.fidelity_param:
        return merged

    value = fidelity_param_value(level, pruning)
    if (
        search_space
        and pruning.fidelity_param in search_space
        and not pruning.fidelity_values
    ):
        spec = search_space[pruning.fidelity_param]
        if spec.low is not None and spec.high is not None:
            span = spec.high - spec.low
            steps = pruning.max_fidelity - pruning.min_fidelity
            if steps > 0:
                frac = (level - pruning.min_fidelity) / steps
                if spec.type == "int":
                    value = int(round(spec.low + span * frac))
                else:
                    value = round(spec.low + span * frac, 6)
    merged[pruning.fidelity_param] = value
    return merged


def fidelity_env(level: int, pruning: PruningConfig) -> dict[str, str]:
    """Environment variables exposed to build commands."""
    param_value = fidelity_param_value(level, pruning) if pruning.fidelity_param else level
    return {
        "AIMAKE_FIDELITY": str(level),
        "AIMAKE_MAX_FIDELITY": str(pruning.max_fidelity),
        "AIMAKE_FIDELITY_PARAM": pruning.fidelity_param or "",
        "AIMAKE_FIDELITY_VALUE": str(param_value),
    }
