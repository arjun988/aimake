"""End-to-end hyperparameter optimization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aimake.config.schema import AimakeConfig, OptimizationConfig
from aimake.experiments.fidelity import apply_fidelity, fidelity_env, fidelity_steps
from aimake.experiments.hyperband import run_hyperband, run_successive_halving
from aimake.experiments.mlflow_export import export_optimization
from aimake.experiments.optuna_search import (
    create_study,
    preview_trials,
    require_optuna,
    suggest_parameters,
)
from aimake.experiments.pareto import extract_numeric_metrics, pareto_front_indices
from aimake.experiments.search import generate_trials
from aimake.execution.runner import BuildRunner
from aimake.graph.dag import Graph
from aimake.metrics.parser import MetricsParser

_BAYESIAN_STRATEGIES = frozenset({"bayesian", "optuna"})


@dataclass
class TrialResult:
    """Result of a single optimization trial."""

    trial_number: int
    parameters: dict[str, Any]
    build_id: int | None
    metrics: dict[str, Any]
    objective_value: float | None
    objective_values: dict[str, float] = field(default_factory=dict)
    success: bool = False
    on_pareto_front: bool = False
    fidelity: int | None = None
    pruned: bool = False


@dataclass
class OptimizationResult:
    """Result of a full optimization run."""

    experiment_id: int
    trials: list[TrialResult] = field(default_factory=list)
    best_trial: TrialResult | None = None
    best_build_id: int | None = None
    best_value: float | None = None
    best_parameters: dict[str, Any] = field(default_factory=dict)
    pareto_front: list[TrialResult] = field(default_factory=list)
    stopped_early: bool = False
    mlflow_run_id: str | None = None
    pruned_trials: int = 0

    @property
    def success(self) -> bool:
        if self.pareto_front:
            return True
        return self.best_trial is not None and self.best_trial.success


class Optimizer:
    """Run hyperparameter search by rebuilding the pipeline per trial."""

    def __init__(
        self,
        project_root,
        config: AimakeConfig,
        cache,
        *,
        debug: bool = False,
        verbose: bool = False,
    ) -> None:
        self.project_root = project_root
        self.config = config
        self.cache = cache
        self.debug = debug
        self.verbose = verbose
        self.db = cache.state_db
        self.metrics_parser = MetricsParser(project_root)

    def run(
        self,
        *,
        trials: int | None = None,
        dry_run: bool = False,
        name: str | None = None,
    ) -> OptimizationResult:
        opt = self._require_optimization_config()
        objective = opt.objective
        assert objective is not None

        metric_artifact = self._resolve_metric_artifact(objective.artifact)
        param_artifact = self._resolve_parameter_artifact(opt.parameter_artifact, metric_artifact)
        max_trials = trials or opt.trials
        metric_names = objective.metric_names()
        directions = objective.metric_directions()
        is_multi = objective.is_multi_objective()

        experiment_name = name or f"{self.config.project.name}-opt"
        experiment_id = self.db.create_experiment(
            experiment_name,
            strategy=opt.strategy,
            objective_metric=",".join(metric_names),
            objective_direction=",".join(directions.values()),
            config={
                "search_space": {k: v.model_dump() for k, v in opt.search_space.items()},
                "parameter_artifact": param_artifact,
                "metric_artifact": metric_artifact,
                "trials": max_trials,
                "early_stopping": opt.early_stopping.model_dump() if opt.early_stopping else None,
                "mlflow": opt.mlflow.model_dump() if opt.mlflow else None,
            },
        )

        result = OptimizationResult(experiment_id=experiment_id)

        if dry_run:
            trial_params_list = self._plan_trials(opt, objective, max_trials)
            for i, params in enumerate(trial_params_list, start=1):
                result.trials.append(
                    TrialResult(
                        trial_number=i,
                        parameters=params,
                        build_id=None,
                        metrics={},
                        objective_value=None,
                        success=True,
                    )
                )
            self.db.finish_experiment(experiment_id, status="planned")
            return result

        if opt.pruning and opt.pruning.enabled and not is_multi:
            if opt.strategy in _BAYESIAN_STRATEGIES:
                self._run_optuna_multifidelity(
                    result,
                    opt,
                    objective,
                    param_artifact,
                    metric_artifact,
                    max_trials,
                    experiment_id,
                    metric_names,
                    directions,
                )
            else:
                self._run_pruning_trials(
                    result,
                    opt,
                    objective,
                    param_artifact,
                    metric_artifact,
                    max_trials,
                    experiment_id,
                    metric_names,
                    directions,
                )
        elif opt.strategy in _BAYESIAN_STRATEGIES:
            self._run_optuna_trials(
                result,
                opt,
                objective,
                param_artifact,
                metric_artifact,
                max_trials,
                experiment_id,
                is_multi,
                metric_names,
                directions,
            )
        else:
            self._run_fixed_trials(
                result,
                opt,
                objective,
                param_artifact,
                metric_artifact,
                max_trials,
                experiment_id,
                is_multi,
                metric_names,
                directions,
            )

        self._finalize_result(result, is_multi, metric_names, directions)

        if opt.mlflow and opt.mlflow.enabled:
            result.mlflow_run_id = export_optimization(
                config=opt.mlflow,
                experiment_name=experiment_name,
                strategy=opt.strategy,
                result=result,
                objective_names=metric_names,
                objective_directions=directions,
            )

        status = "success" if result.success else "failed"
        self.db.finish_experiment(
            experiment_id,
            status=status,
            best_build_id=result.best_build_id,
            best_value=result.best_value,
        )
        return result

    def _plan_trials(
        self,
        opt: OptimizationConfig,
        objective,
        max_trials: int,
    ) -> list[dict[str, Any]]:
        if opt.strategy in _BAYESIAN_STRATEGIES:
            return preview_trials(
                objective,
                opt.search_space,
                strategy=opt.strategy,
                max_trials=max_trials,
                seed=opt.seed,
                pruning=opt.pruning,
            )
        strategy = "random" if opt.strategy == "hyperband" else opt.strategy
        return generate_trials(
            opt.search_space,
            strategy=strategy,
            max_trials=max_trials,
            seed=opt.seed,
        )

    def _run_fixed_trials(
        self,
        result: OptimizationResult,
        opt: OptimizationConfig,
        objective,
        param_artifact: str,
        metric_artifact: str,
        max_trials: int,
        experiment_id: int,
        is_multi: bool,
        metric_names: list[str],
        directions: dict[str, str],
    ) -> None:
        trial_params_list = self._plan_trials(opt, objective, max_trials)
        if not trial_params_list:
            raise ValueError("No trials generated from search space")

        best_value: float | None = None
        best_trial: TrialResult | None = None
        trials_since_improvement = 0
        previous_pareto_size = 0
        es = opt.early_stopping

        for i, params in enumerate(trial_params_list, start=1):
            trial = self._run_trial(
                i,
                params,
                param_artifact,
                metric_artifact,
                experiment_id,
                metric_names,
                directions,
                is_multi,
            )
            result.trials.append(trial)
            self._save_trial_record(experiment_id, trial)

            if trial.success:
                if is_multi:
                    current_front = self._compute_pareto_indices(result.trials, metric_names, directions)
                    if len(current_front) > previous_pareto_size:
                        previous_pareto_size = len(current_front)
                        trials_since_improvement = 0
                    else:
                        trials_since_improvement += 1
                elif trial.objective_value is not None:
                    if self._is_improvement(
                        trial.objective_value,
                        best_value,
                        directions[metric_names[0]],
                        es.min_delta if es and es.enabled else 0.0,
                    ):
                        best_value = trial.objective_value
                        best_trial = trial
                        result.best_build_id = trial.build_id
                        result.best_parameters = dict(trial.parameters)
                        trials_since_improvement = 0
                    else:
                        trials_since_improvement += 1

            if self._should_stop_early(es, i, trials_since_improvement):
                result.stopped_early = True
                break

        result.best_trial = best_trial
        result.best_value = best_value

    def _run_pruning_trials(
        self,
        result: OptimizationResult,
        opt: OptimizationConfig,
        objective,
        param_artifact: str,
        metric_artifact: str,
        max_trials: int,
        experiment_id: int,
        metric_names: list[str],
        directions: dict[str, str],
    ) -> None:
        assert opt.pruning is not None
        configs = self._plan_trials(opt, objective, max_trials)
        if not configs:
            raise ValueError("No trials generated from search space")

        direction = directions[metric_names[0]]
        trial_counter = 0

        def evaluate(params: dict[str, Any], level: int, _num: int) -> TrialResult:
            nonlocal trial_counter
            trial_counter += 1
            scaled = apply_fidelity(params, level, opt.pruning, opt.search_space)
            return self._run_trial(
                trial_counter,
                scaled,
                param_artifact,
                metric_artifact,
                experiment_id,
                metric_names,
                directions,
                is_multi=False,
                fidelity=level,
                pruning=opt.pruning,
            )

        if opt.pruning.strategy == "hyperband":
            halving = run_hyperband(
                configs,
                evaluate,
                opt.pruning,
                direction=direction,
                seed=opt.seed,
            )
        else:
            halving = run_successive_halving(
                configs,
                evaluate,
                opt.pruning,
                direction=direction,
                seed=opt.seed,
            )

        for trial in halving.trials:
            result.trials.append(trial)
            self._save_trial_record(experiment_id, trial)
        result.pruned_trials = halving.pruned_count
        result.best_trial = halving.best_trial
        result.best_value = halving.best_value
        if halving.best_trial:
            result.best_build_id = halving.best_trial.build_id
            result.best_parameters = dict(halving.best_trial.parameters)

    def _run_optuna_multifidelity(
        self,
        result: OptimizationResult,
        opt: OptimizationConfig,
        objective,
        param_artifact: str,
        metric_artifact: str,
        max_trials: int,
        experiment_id: int,
        metric_names: list[str],
        directions: dict[str, str],
    ) -> None:
        optuna = require_optuna()
        from optuna.exceptions import TrialPruned

        study = create_study(
            objective,
            strategy=opt.strategy,
            seed=opt.seed,
            pruning=opt.pruning,
        )
        trial_counter = 0
        best_value: float | None = None
        best_trial: TrialResult | None = None
        direction = directions[metric_names[0]]
        pruning = opt.pruning
        assert pruning is not None

        def objective_fn(optuna_trial) -> float:
            nonlocal trial_counter, best_value, best_trial
            trial_counter += 1
            params = suggest_parameters(optuna_trial, opt.search_space)
            last_value: float | None = None

            for level in fidelity_steps(pruning):
                scaled = apply_fidelity(params, level, pruning, opt.search_space)
                trial = self._run_trial(
                    trial_counter,
                    scaled,
                    param_artifact,
                    metric_artifact,
                    experiment_id,
                    metric_names,
                    directions,
                    is_multi=False,
                    fidelity=level,
                    pruning=pruning,
                )
                result.trials.append(trial)
                self._save_trial_record(experiment_id, trial)

                if not trial.success or trial.objective_value is None:
                    raise TrialPruned()

                last_value = trial.objective_value
                optuna_trial.report(last_value, level)
                if optuna_trial.should_prune():
                    trial.pruned = True
                    result.pruned_trials += 1
                    raise TrialPruned()

            if last_value is not None and (
                best_value is None or self._is_improvement(last_value, best_value, direction, 0.0)
            ):
                best_value = last_value
                best_trial = result.trials[-1]
                result.best_build_id = best_trial.build_id
                result.best_parameters = dict(params)
            return last_value  # type: ignore[return-value]

        study.optimize(objective_fn, n_trials=max_trials)
        result.best_trial = best_trial
        result.best_value = best_value

    def _run_optuna_trials(
        self,
        result: OptimizationResult,
        opt: OptimizationConfig,
        objective,
        param_artifact: str,
        metric_artifact: str,
        max_trials: int,
        experiment_id: int,
        is_multi: bool,
        metric_names: list[str],
        directions: dict[str, str],
    ) -> None:
        study = create_study(objective, strategy=opt.strategy, seed=opt.seed, pruning=opt.pruning)
        best_value: float | None = None
        best_trial: TrialResult | None = None
        trials_since_improvement = 0
        previous_pareto_size = 0
        es = opt.early_stopping

        for i in range(1, max_trials + 1):
            optuna_trial = study.ask()
            params = suggest_parameters(optuna_trial, opt.search_space)
            trial = self._run_trial(
                i,
                params,
                param_artifact,
                metric_artifact,
                experiment_id,
                metric_names,
                directions,
                is_multi,
            )
            result.trials.append(trial)
            self._save_trial_record(experiment_id, trial)

            if trial.success and trial.objective_values:
                values = [trial.objective_values[name] for name in metric_names]
                if len(values) > 1:
                    study.tell(optuna_trial, values)
                else:
                    study.tell(optuna_trial, values[0])
            else:
                # Penalize failed trials so Optuna learns to avoid bad regions
                penalty = -1e9 if directions[metric_names[0]] == "maximize" else 1e9
                if is_multi:
                    study.tell(optuna_trial, [penalty] * len(metric_names))
                else:
                    study.tell(optuna_trial, penalty)

            if trial.success:
                if is_multi:
                    current_front = self._compute_pareto_indices(result.trials, metric_names, directions)
                    if len(current_front) > previous_pareto_size:
                        previous_pareto_size = len(current_front)
                        trials_since_improvement = 0
                    else:
                        trials_since_improvement += 1
                elif trial.objective_value is not None:
                    if self._is_improvement(
                        trial.objective_value,
                        best_value,
                        directions[metric_names[0]],
                        es.min_delta if es and es.enabled else 0.0,
                    ):
                        best_value = trial.objective_value
                        best_trial = trial
                        result.best_build_id = trial.build_id
                        result.best_parameters = dict(trial.parameters)
                        trials_since_improvement = 0
                    else:
                        trials_since_improvement += 1

            if self._should_stop_early(es, i, trials_since_improvement):
                result.stopped_early = True
                break

        result.best_trial = best_trial
        result.best_value = best_value

    def _run_trial(
        self,
        trial_number: int,
        params: dict[str, Any],
        param_artifact: str,
        metric_artifact: str,
        experiment_id: int,
        metric_names: list[str],
        directions: dict[str, str],
        is_multi: bool,
        *,
        fidelity: int | None = None,
        pruning=None,
    ) -> TrialResult:
        trial_config = self._apply_parameters(param_artifact, params)
        graph = Graph.from_config(trial_config)
        runner = BuildRunner(
            self.project_root,
            trial_config,
            graph,
            self.cache,
            jobs=trial_config.project.jobs,
            debug=self.debug,
            verbose=self.verbose,
        )
        fenv: dict[str, str] = {}
        max_fid = None
        if fidelity is not None and pruning is not None:
            fenv = fidelity_env(fidelity, pruning)
            max_fid = pruning.max_fidelity
        build_result = runner.build(
            targets=[metric_artifact],
            force={metric_artifact},
            build_parameters=params,
            experiment_id=experiment_id,
            trial_number=trial_number,
            fidelity_level=fidelity,
            max_fidelity=max_fid,
            fidelity_env=fenv,
        )

        metrics = self._collect_metrics(trial_config, metric_artifact, build_result.metrics)
        objective_values = extract_numeric_metrics(metrics, metric_names) or {}
        objective_value: float | None = None
        if not is_multi and metric_names:
            objective_value = objective_values.get(metric_names[0])

        return TrialResult(
            trial_number=trial_number,
            parameters=params,
            build_id=build_result.build_id if build_result.success else None,
            metrics=metrics,
            objective_value=objective_value,
            objective_values=objective_values,
            success=build_result.success and bool(objective_values),
            fidelity=fidelity,
        )

    def _save_trial_record(self, experiment_id: int, trial: TrialResult) -> None:
        self.db.save_trial(
            experiment_id,
            trial.trial_number,
            build_id=trial.build_id,
            parameters=trial.parameters,
            metrics=trial.metrics,
            objective_value=trial.objective_value,
            status="success" if trial.success else "failed",
        )

    def _finalize_result(
        self,
        result: OptimizationResult,
        is_multi: bool,
        metric_names: list[str],
        directions: dict[str, str],
    ) -> None:
        if is_multi:
            front_indices = self._compute_pareto_indices(result.trials, metric_names, directions)
            result.pareto_front = []
            for idx in front_indices:
                trial = result.trials[idx]
                trial.on_pareto_front = True
                result.pareto_front.append(trial)
            if result.pareto_front and not result.best_trial:
                result.best_trial = result.pareto_front[0]
                result.best_build_id = result.best_trial.build_id
                result.best_parameters = dict(result.best_trial.parameters)

    @staticmethod
    def _compute_pareto_indices(
        trials: list[TrialResult],
        metric_names: list[str],
        directions: dict[str, str],
    ) -> list[int]:
        successful = [
            (i, trial)
            for i, trial in enumerate(trials)
            if trial.success and trial.objective_values
        ]
        metric_rows = [trial.objective_values for _, trial in successful]
        front_local = pareto_front_indices(metric_rows, directions)
        return [successful[i][0] for i in front_local]

    @staticmethod
    def _should_stop_early(
        es,
        trial_number: int,
        trials_since_improvement: int,
    ) -> bool:
        if not es or not es.enabled:
            return False
        if trial_number < es.min_trials:
            return False
        return trials_since_improvement >= es.patience

    @staticmethod
    def _is_improvement(
        value: float,
        best: float | None,
        direction: str,
        min_delta: float,
    ) -> bool:
        if best is None:
            return True
        if direction == "maximize":
            return value > best + min_delta
        return value < best - min_delta

    def _require_optimization_config(self) -> OptimizationConfig:
        if not self.config.optimization:
            raise ValueError(
                "No optimization block in aimake.yaml. "
                "Add an 'optimization' section with search_space and objective."
            )
        return self.config.optimization

    def _resolve_metric_artifact(self, explicit: str | None) -> str:
        if explicit:
            if explicit not in self.config.artifacts:
                raise ValueError(f"Objective artifact '{explicit}' not found")
            return explicit

        for name, artifact in self.config.artifacts.items():
            if artifact.type == "evaluation" and artifact.metrics and artifact.metrics.file:
                return name
        for name, artifact in self.config.artifacts.items():
            if artifact.metrics and artifact.metrics.file:
                return name
        raise ValueError(
            "Could not detect metric artifact. Set optimization.objective.artifact explicitly."
        )

    def _resolve_parameter_artifact(self, explicit: str | None, metric_artifact: str) -> str:
        if explicit:
            if explicit not in self.config.artifacts:
                raise ValueError(f"Parameter artifact '{explicit}' not found")
            return explicit
        return metric_artifact

    def _apply_parameters(self, artifact_name: str, params: dict[str, Any]) -> AimakeConfig:
        config = self.config.model_copy(deep=True)
        config.artifacts[artifact_name].parameters.update(params)
        return config

    def _collect_metrics(
        self,
        config: AimakeConfig,
        artifact_name: str,
        build_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        metrics = dict(build_metrics)
        artifact = config.artifacts[artifact_name]
        if artifact.metrics and artifact.metrics.file:
            file_metrics = self.metrics_parser.parse_file(artifact.metrics.file)
            metrics.update(file_metrics)
        return metrics
