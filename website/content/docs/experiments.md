---
title: Experiments
description: Compare builds, hyperparameter optimize with grid/random/bayesian/optuna, Hyperband pruning, Pareto multi-objective, and MLflow export.
---

aimake treats hyperparameter search as **repeated incremental builds** over a search space. Each trial injects parameters as environment variables, reuses cached upstream artifacts, and records metrics for compare / Pareto / MLflow.

Related: [CLI reference](/docs/cli#experiments), [Artifact registry](/docs/registry), [Dashboard](/docs/dashboard).

## Compare builds

```bash
aimake compare                    # previous vs latest
aimake compare 3 5                # build #3 vs #5
aimake compare latest previous
```

| Argument | Description |
|----------|-------------|
| `baseline` | Build id, `latest`, or `previous` (default `previous`) |
| `candidate` | Build id, `latest`, or `previous` (default `latest`) |

The CLI prints metric deltas (accuracy, cost, latency, …) from stored build history. The dashboard **Experiments** page exposes the same compare flow via the API.

## Hyperparameter optimization

### Config

```yaml
optimization:
  trials: 5
  strategy: grid          # grid | random | bayesian | optuna | hyperband
  parameter_artifact: evaluation
  seed: 42
  search_space:
    temperature:
      type: float
      low: 0.8
      high: 1.2
      step: 0.2
    top_k:
      type: int
      low: 3
      high: 10
    prompt_variant:
      type: categorical
      choices: [v1, v2, v3]
  objective:
    metric: accuracy
    direction: maximize
    artifact: evaluation
```

| Field | Description |
|-------|-------------|
| `trials` | Max trials (CLI `--trials` can override) |
| `strategy` | `grid`, `random`, `bayesian`, `optuna`, or `hyperband` |
| `parameter_artifact` | Artifact whose rebuild receives trial params |
| `search_space` | Named params (`float` / `int` / `categorical`) |
| `objective` | Metric + direction (+ optional multi-metric — see Pareto) |
| `seed` | Optional RNG seed for reproducibility |

### Search space types

| `type` | Fields |
|--------|--------|
| `float` | `low`, `high`, optional `step` |
| `int` | `low`, `high`, optional `step` |
| `categorical` | `choices: [...]` |

### CLI

```bash
aimake optimize
aimake optimize --dry-run
aimake optimize -n 20 --name tuning-v2
aimake experiments list
aimake experiments list --limit 50
aimake experiments show 1
```

| Command / option | Description |
|------------------|-------------|
| `optimize` | Run the search defined in yaml |
| `--trials`, `-n` | Override trial count |
| `--dry-run` | Show planned trials without building |
| `--name` | Experiment display name |
| `experiments list` | Recent optimization runs |
| `experiments show <id>` | Per-trial params, metrics, objective |

### Trial parameters in your code

Parameters are injected as `AIMAKE_PARAM_<NAME>` (uppercased):

```python
import os

temperature = float(os.environ.get("AIMAKE_PARAM_TEMPERATURE", "1.0"))
top_k = int(os.environ.get("AIMAKE_PARAM_TOP_K", "5"))
variant = os.environ.get("AIMAKE_PARAM_PROMPT_VARIANT", "v1")
```

Upstream artifacts that do not depend on those params stay **SKIP** / **RESTORE** — only the swept subgraph rebuilds.

## Strategies

| Strategy | Extra | Notes |
|----------|-------|-------|
| `grid` | — | Full cartesian product (respects `trials` cap) |
| `random` | — | Uniform samples from the space |
| `bayesian` | — | Built-in Bayesian optimization |
| `optuna` | `pip install aimake[optuna]` | TPE / Optuna sampler |
| `hyperband` | often with Optuna pruning | Multi-fidelity / Hyperband-style |

```yaml
optimization:
  strategy: optuna
  trials: 20
  # ...
```

## Early stopping

```yaml
optimization:
  strategy: optuna
  trials: 40
  early_stopping:
    enabled: true
    patience: 5
    min_trials: 10
    min_delta: 0.001
  objective:
    metric: accuracy
    direction: maximize
    artifact: evaluation
  search_space:
    # ...
```

Stops when the objective does not improve by `min_delta` for `patience` trials after `min_trials`.

## Pareto / multi-objective

Optimize several metrics at once (e.g. maximize quality, minimize cost):

```yaml
optimization:
  strategy: optuna
  trials: 30
  search_space:
    temperature:
      type: float
      low: 0.5
      high: 1.5
  objective:
    metrics: [accuracy, cost_usd]
    directions: [maximize, minimize]
    artifact: evaluation
```

| Field | Description |
|-------|-------------|
| `objective.metrics` | List of metric names |
| `objective.directions` | Parallel list of `maximize` / `minimize` |
| `objective.artifact` | Artifact that emits those metrics |

Single-objective form (`metric` + `direction`) remains supported. Results surface as Pareto-aware trial summaries in the CLI and experiment history.

## Hyperband & multi-fidelity pruning

```yaml
optimization:
  strategy: optuna
  trials: 24
  pruning:
    enabled: true
    strategy: hyperband       # or successive_halving
    min_fidelity: 1
    max_fidelity: 3
    reduction_factor: 3
    fidelity_param: epochs
    fidelity_values: [1, 5, 10]
  search_space:
    learning_rate:
      type: float
      low: 1.0e-5
      high: 1.0e-3
  objective:
    metric: accuracy
    direction: maximize
    artifact: evaluation
```

| Field | Description |
|-------|-------------|
| `pruning.strategy` | `hyperband` or `successive_halving` |
| `min_fidelity` / `max_fidelity` | Fidelity rung bounds |
| `reduction_factor` | Bracket reduction (≥ 2) |
| `fidelity_param` | Logical name for the fidelity knob |
| `fidelity_values` | One value per fidelity level |

Training scripts should read:

| Env var | Meaning |
|---------|---------|
| `AIMAKE_FIDELITY` | Current fidelity index |
| `AIMAKE_FIDELITY_VALUE` | Mapped value (e.g. epoch count) |
| `AIMAKE_MAX_FIDELITY` | Max fidelity index |

Low-fidelity trials can be pruned early so GPU budget goes to promising configs.

## MLflow export

```yaml
optimization:
  strategy: optuna
  trials: 15
  mlflow:
    enabled: true
    tracking_uri: http://localhost:5000
    experiment_name: my-rag-tuning
  search_space:
    # ...
  objective:
    metric: accuracy
    direction: maximize
    artifact: evaluation
```

```bash
pip install aimake[mlflow]
aimake optimize --name sweep-mlflow
```

| Field | Description |
|-------|-------------|
| `mlflow.enabled` | Turn on export |
| `mlflow.tracking_uri` | MLflow tracking server |
| `mlflow.experiment_name` | Experiment name in MLflow |

Trial params and metrics are logged so you can use the MLflow UI alongside `aimake experiments show`. For pipeline-level lineage (not just optimization), see [Trust — lineage](/docs/trust#lineage-export).

## End-to-end workflow

```bash
# 1. Preview the sweep
aimake optimize --dry-run

# 2. Run
aimake optimize -n 12 --name temp-sweep

# 3. Inspect
aimake experiments list
aimake experiments show 1
aimake compare previous latest

# 4. Promote the winner (optional)
aimake registry tag evaluation v7 best
aimake registry promote evaluation v7 --stage production
```

## Related

- [CLI reference](/docs/cli)
- [Artifact registry](/docs/registry)
- [Dashboard — Experiments](/docs/dashboard)
- [Plugins / MLflow](/docs/plugins)
