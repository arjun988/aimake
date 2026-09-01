"""Export optimization results to MLflow."""

from __future__ import annotations

from typing import Any

from aimake.config.schema import MLflowConfig


def require_mlflow():
    try:
        import mlflow
    except ImportError as e:
        raise ImportError(
            "MLflow export requires mlflow. Install with: pip install aimake[mlflow]"
        ) from e
    return mlflow


def export_optimization(
    *,
    config: MLflowConfig,
    experiment_name: str,
    strategy: str,
    result: Any,
    objective_names: list[str],
    objective_directions: dict[str, str],
) -> str | None:
    """Log all trials to MLflow; return parent run ID."""
    if not config.enabled:
        return None

    mlflow = require_mlflow()
    if config.tracking_uri:
        mlflow.set_tracking_uri(config.tracking_uri)
    if config.registry_uri:
        mlflow.set_registry_uri(config.registry_uri)

    exp_name = config.experiment_name or experiment_name
    mlflow.set_experiment(exp_name)

    with mlflow.start_run(run_name=experiment_name) as parent:
        mlflow.set_tags(
            {
                "aimake.strategy": strategy,
                "aimake.experiment_id": str(result.experiment_id),
                "aimake.stopped_early": str(result.stopped_early),
            }
        )
        if result.best_value is not None:
            mlflow.log_metric("best_objective", result.best_value)
        if result.pareto_front:
            mlflow.log_metric("pareto_front_size", len(result.pareto_front))

        for trial in result.trials:
            run_name = f"trial-{trial.trial_number}"
            with mlflow.start_run(run_name=run_name, nested=True):
                mlflow.log_params({str(k): v for k, v in trial.parameters.items()})
                numeric_metrics = {
                    k: float(v) for k, v in trial.metrics.items() if isinstance(v, (int, float))
                }
                if numeric_metrics:
                    mlflow.log_metrics(numeric_metrics)
                if trial.objective_value is not None:
                    mlflow.log_metric("objective", trial.objective_value)
                if trial.objective_values:
                    for name, value in trial.objective_values.items():
                        mlflow.log_metric(f"objective_{name}", value)
                mlflow.set_tags(
                    {
                        "aimake.trial": str(trial.trial_number),
                        "aimake.build_id": str(trial.build_id or ""),
                        "aimake.success": str(trial.success),
                        "aimake.pareto": str(trial in result.pareto_front),
                    }
                )

        return parent.info.run_id
