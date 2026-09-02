---
title: Writing aimake.yaml
description: Complete guide to aimake.yaml — project settings, artifacts, inputs, environment, external pins, validation, quality gates, and more.
---

## Overview

`aimake.yaml` is the single source of truth for your pipeline. It declares:

- Project metadata and global behavior
- The artifact DAG (`depends_on`, `command`, `outputs`)
- Metrics, quality gates, and cost estimates
- Optional cache, registry, plugins, optimization, workers, and trust settings

Create one with `aimake init`, or start from [`examples/rag/aimake.yaml`](https://github.com/arjun988/aimake/tree/main/examples/rag).

## Minimal example

```yaml
project:
  name: my-rag-app
  version: "1.0"

artifacts:

  dataset:
    type: dataset
    source: data/train.jsonl

  processed:
    type: dataset
    depends_on: [dataset]
    command: python src/preprocess.py
    outputs:
      - build/processed/

  embeddings:
    type: embedding
    depends_on: [processed]
    command: python src/embed.py
    outputs:
      - build/embeddings/

  prompt:
    type: prompt
    source: prompts/system.txt

  evaluation:
    type: evaluation
    depends_on: [embeddings, prompt]
    command: python src/evaluate.py
    outputs:
      - build/evaluation/
    metrics:
      file: build/evaluation/results.json

quality_gates:
  accuracy:
    minimum: 0.90
  latency_ms:
    maximum: 500
```

## Project block

```yaml
project:
  name: rag-example
  version: "1.0"
  atomic_outputs: true
  environment_mode: names   # or values
  gpus: 2                   # local GPUs (0 = auto-detect)
```

| Field | Purpose |
|-------|---------|
| `name` / `version` | Human-facing project identity |
| `atomic_outputs` | Discard partial outputs on failed commands |
| `environment_mode` | Whether env **names** or **values** enter fingerprints |
| `gpus` | Local GPU pool size for scheduling |

Volatile variables can be excluded with `volatile_environment` (see environment section below).

## Artifacts

### Source artifacts

Tracked inputs without a build command:

```yaml
prompt:
  type: prompt
  source: prompts/system.txt

dataset:
  type: dataset
  source: data/train.jsonl
```

### Command artifacts

```yaml
preprocess:
  type: dataset
  depends_on:
    - dataset
  command: python src/preprocess.py
  outputs:
    - build/processed/
```

### Artifact types

| Type | Description |
|------|-------------|
| `dataset` | Training / evaluation data |
| `model` | Model weights or configuration |
| `prompt` | Prompt templates |
| `embedding` | Vector embeddings |
| `vector_index` | Search indexes |
| `evaluation` | Evaluation runs and metrics |
| `report` | Generated reports |
| `generic` | Any other artifact |

### Common fields

| Field | Description |
|-------|-------------|
| `depends_on` | List of upstream artifact names |
| `command` | Shell command to produce outputs |
| `outputs` | Paths (files or directories) produced by the command |
| `source` | Primary input path for source-like artifacts |
| `inputs` | Extra tracked paths / globs |
| `parameters` | Structured knobs included in fingerprints |
| `environment` | Env var names relevant to this artifact |
| `metrics` | Where to read evaluation metrics |
| `external` | Remote model / API pins |
| `validation` | Structural and custom output checks |
| `cost_estimate` | Estimated USD / tokens for `aimake plan` |
| `resources` | e.g. `gpu: 1` |
| `worker` | Named remote worker |
| `metadata` | Plugin-specific config (HF, W&B, DVC, Docker, Ollama) |

## Input tracking

Global or per-artifact inputs support globs:

```yaml
inputs:
  - data/train.jsonl
  - prompts/system.txt
  - data/**          # glob patterns supported
```

Anything listed participates in fingerprinting when it affects the artifact.

## Environment variables

```yaml
environment:
  - MODEL_NAME
  - API_VERSION
```

- Default `environment_mode: names` — changing which variables are declared invalidates; values do not (safer for secrets churn).
- Use `environment_mode: values` when value changes must bust the cache.
- Exclude noisy vars with `volatile_environment`.

Secrets providers (Vault / Doppler / 1Password / `.env`) are configured under `secrets:` — `aimake secrets` lists loaded **key names only**. See [Team & production](/docs/team).

## External dependencies

Pin remote models so provider-side changes invalidate downstream steps:

```yaml
artifacts:
  embeddings:
    external:
      - name: openai-embeddings
        provider: openai
        model: text-embedding-3-small
        revision: "2024-01"   # bump when the remote model changes
```

With probes (v1.6+):

```yaml
external:
  - name: llm
    provider: openai
    model: gpt-4o
    revision: "…"
    probe: true
    probe_mode: warn   # or invalidate
```

Mark accepted nondeterminism with `volatile: true` (excluded from fingerprints). Run `aimake probe` in CI.

## Metrics, validation, and cost

```yaml
evaluation:
  type: evaluation
  depends_on: [index, prompt]
  command: python src/evaluate.py
  outputs:
    - build/evaluation/
  parameters:
    temperature: 1.0
  metrics:
    file: build/evaluation/results.json
  external:
    - name: embedder
      provider: local
      model: deterministic-hash-embedder
      revision: "v1"
  validation:
    non_empty: true
    min_size_bytes: 10
    required_keys: [accuracy, f1, cost_usd]
    min_value:
      accuracy: 0.01
    revalidate_on_cache_hit: true
    command: python scripts/check_eval.py
  cost_estimate:
    cost_usd: 0.42
    tokens: 1200
```

Scripts can write to staged paths with:

```python
from aimake.utils.outputs import resolve_output
```

## Quality gates

```yaml
quality_gates:
  accuracy:
    minimum: 0.80
    required: true
  latency_ms:
    maximum: 1000
  cost_usd:
    maximum: 1.00
    required: true
```

```bash
aimake eval --check
```

`required: true` fails when the metric is missing entirely — important for CI reliability.

## Remote cache

```yaml
cache:
  remote:
    type: s3
    auto_pull: true
    auto_push: true
    team_id: acme
    s3:
      bucket: my-aimake-cache
      prefix: projects/my-rag-app/
      region: us-east-1
      # endpoint_url: https://minio.example.com  # S3-compatible
```

Requires `pip install aimake[s3]`. Setup helper:

```bash
aimake cache remote-init --bucket my-org-cache --team acme --region us-east-1
```

Details: [Fingerprints & caching](/docs/caching), [Remote & team cache](/docs/remote-cache).

## GPU scheduling and workers

```yaml
project:
  gpus: 2

artifacts:
  embeddings:
    type: embedding
    resources:
      gpu: 1
    command: python src/embed.py
    outputs:
      - build/embeddings/
    worker: gpu-node-1

workers:
  enabled: true
  workers:
    - name: gpu-node-1
      host: 10.0.0.5
      user: build
      gpus: 2
      jobs: 2
      workdir: /home/build/my-rag-app
```

```bash
aimake workers
```

See [GPU & workers](/docs/workers).

## Optimization

```yaml
optimization:
  trials: 5
  strategy: grid          # grid | random | bayesian | optuna | hyperband
  parameter_artifact: evaluation
  search_space:
    temperature:
      type: float
      low: 0.8
      high: 1.2
      step: 0.2
  objective:
    metric: accuracy
    direction: maximize
    artifact: evaluation
```

Trial parameters arrive as `AIMAKE_PARAM_*` environment variables. Advanced Optuna / MLflow / Hyperband options are documented under [Experiments](/docs/experiments).

## Artifact registry

```yaml
registry:
  enabled: true
  auto_register: true
  default_stage: dev
```

Optional remote push targets and `policy.promote` gates are covered in [Artifact registry](/docs/registry).

## Plugins (sketch)

Enable under `plugins.*.enabled: true` and attach per-artifact `metadata`:

```yaml
plugins:
  huggingface:
    enabled: true
    token_env: HF_TOKEN
  wandb:
    enabled: true
    project: my-rag-app
  dvc:
    enabled: true
  docker:
    enabled: true
  ollama:
    enabled: true
```

Full examples: [Plugins overview](/docs/plugins).

## Trust surfaces (v1.6+)

```yaml
attestation:
  enabled: true
lineage:
  enabled: true
  formats: [openlineage, mlflow]
  auto_export_on_build: true
```

See [Trust & reproducibility](/docs/trust).

## Config path and global CLI flags

```bash
aimake build --config path/to/aimake.yaml
aimake -c path/to/aimake.yaml plan
```

| Global option | Description |
|---------------|-------------|
| `--version`, `-V` | Print version and exit |
| `--config`, `-c` | Path to `aimake.yaml` |

## Next steps

- [How aimake works](/docs/how-it-works) — runtime pipeline
- [Fingerprints & caching](/docs/caching) — what invalidates what
- [Quick start](/docs/quick-start) — run `examples/rag`
- [CLI reference](/docs/cli) — command options
