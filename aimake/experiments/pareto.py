"""Pareto front utilities for multi-objective optimization."""

from __future__ import annotations

from typing import Any


def _better(value: float, other: float, direction: str) -> bool:
    if direction == "maximize":
        return value > other
    return value < other


def _at_least_as_good(value: float, other: float, direction: str) -> bool:
    if direction == "maximize":
        return value >= other
    return value <= other


def dominates(
    a_metrics: dict[str, float],
    b_metrics: dict[str, float],
    directions: dict[str, str],
) -> bool:
    """Return True if *a* Pareto-dominates *b*."""
    metric_names = list(directions.keys())
    if not metric_names:
        return False

    strictly_better = False
    for name in metric_names:
        a_val = a_metrics.get(name)
        b_val = b_metrics.get(name)
        if a_val is None or b_val is None:
            return False
        if not _at_least_as_good(a_val, b_val, directions[name]):
            return False
        if _better(a_val, b_val, directions[name]):
            strictly_better = True
    return strictly_better


def extract_numeric_metrics(metrics: dict[str, Any], names: list[str]) -> dict[str, float] | None:
    """Extract objective metric values; return None if any are missing."""
    result: dict[str, float] = {}
    for name in names:
        value = metrics.get(name)
        if not isinstance(value, (int, float)):
            return None
        result[name] = float(value)
    return result


def pareto_front_indices(
    metric_rows: list[dict[str, float]],
    directions: dict[str, str],
) -> list[int]:
    """Return indices of non-dominated trials."""
    front: list[int] = []
    for i, metrics_i in enumerate(metric_rows):
        dominated = False
        for j, metrics_j in enumerate(metric_rows):
            if i == j:
                continue
            if dominates(metrics_j, metrics_i, directions):
                dominated = True
                break
        if not dominated:
            front.append(i)
    return front
