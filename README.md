<div align="center">

# aimake

**The incremental build system for AI applications.**

[![PyPI](https://img.shields.io/pypi/v/aimake?label=PyPI&color=blue)](https://pypi.org/project/aimake/)
[![Python](https://img.shields.io/pypi/pyversions/aimake?label=Python)](https://pypi.org/project/aimake/)
[![Downloads](https://img.shields.io/pypi/dm/aimake?label=Downloads)](https://pypi.org/project/aimake/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![CI](https://github.com/arjun988/aimake/actions/workflows/ci.yml/badge.svg)](https://github.com/arjun988/aimake/actions/workflows/ci.yml)

*Like `make` + `git` + DVC — but designed for AI/ML pipelines.*

[Docs](website/README.md) · [Installation](#installation) · [Quick Start](#quick-start) · [CLI Reference](#cli-reference) · [Migration](#migration) · [Comparison](docs/COMPARISON.md) · [Adapters](docs/ADAPTERS.md)

</div>

---

## Table of contents

- [Why aimake?](#why-aimake)
- [Features](#features)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Example workflow](#example-workflow)
- [How it works](#how-it-works)
- [CLI reference](#cli-reference)
- [Configuration](#configuration)
- [Remote cache (S3)](#remote-cache-s3)
- [GPU scheduling & workers](#gpu-scheduling--workers)
- [Artifact diffs](#artifact-diffs)
- [Experiments & optimization](#experiments--optimization)
- [Artifact registry](#artifact-registry)
- [Hugging Face plugin](#hugging-face-plugin)
- [Weights & Biases plugin](#weights--biases-plugin)
- [DVC plugin](#dvc-plugin)
- [Docker plugin](#docker-plugin)
- [Ollama plugin](#ollama-plugin)
- [Python API](#python-api)
- [CI/CD](#cicd)
- [Architecture](#architecture)
- [Development](#development)
- [Security](#security)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Why aimake?

Traditional build tools understand `source → object → binary`. AI pipelines are different:

```text
dataset
   │
   ▼
preprocess
   │
   ▼
embeddings
   │
   ▼
index ─────────────┐
                   │
prompt ────────────┼──► evaluation
                             │
                             ▼
                           report
```

When only a prompt changes, everything upstream should be **skipped**. `aimake` tracks dependencies between datasets, models, prompts, embeddings, indexes, evaluations, and generated artifacts — rebuilding only what actually changed.

| Tool | Focus |
|------|-------|
| **Make** | Generic file dependencies |
| **DVC** | Data versioning |
| **MLflow** | Experiment tracking |
| **aimake** | Incremental AI pipeline builds with content-addressable caching |

---

## Features

| Category | Capabilities |
|----------|-------------|
| **Core** | Dependency DAG, SHA-256 fingerprinting, parallel builds, content-addressable cache |
| **CLI** | 25+ commands for build, plan, inspect, diff, compare, optimize, registry |
| **Cache** | Local SQLite + filesystem; optional S3 remote (`push` / `pull` / `sync`) |
| **Compute** | GPU-aware scheduling, distributed SSH workers |
| **Experiments** | Grid/random/Bayesian/Optuna search, Hyperband pruning, Pareto multi-objective |
| **Integrations** | MLflow export, Hugging Face Hub, W&B, DVC, Docker, Ollama, artifact registry |
| **CI** | Quality gates, `doctor` health checks, `eval --check` for pipelines |

---

## Installation

```bash
pip install aimake
```

Published on [PyPI](https://pypi.org/project/aimake/).

Or with [pipx](https://pipx.pypa.io/) for an isolated CLI:

```bash
pipx install aimake
```

**Requirements:** Python 3.11+

### Optional extras

| Extra | Install | Enables |
|-------|---------|---------|
| `s3` | `pip install aimake[s3]` | S3 remote cache (`boto3`) |
| `huggingface` | `pip install aimake[huggingface]` | `aimake hf` commands |
| `wandb` | `pip install aimake[wandb]` | Weights & Biases logging |
| `dvc` | `pip install aimake[dvc]` | DVC pull/push (`dvc` CLI) |
| `docker` | Docker Desktop / CLI | Containerized builds |
| `ollama` | [Ollama](https://ollama.com/) CLI | Local LLM model pull |
| `plugins` | `pip install aimake[plugins]` | HF + W&B + DVC |
| `optuna` | `pip install aimake[optuna]` | Bayesian / Optuna optimization |
| `mlflow` | `pip install aimake[mlflow]` | MLflow trial export |
| `experiments` | `pip install aimake[experiments]` | Optuna + MLflow |
| `all` | `pip install aimake[all]` | Everything above + dev tools |
| `dev` | `pip install aimake[dev]` | pytest, coverage |

---

## Quick start

```bash
aimake init          # scaffold aimake.yaml + .aimake/
aimake plan          # preview what will run
aimake build         # incremental build
aimake status        # artifact freshness
aimake graph         # dependency DAG
```

### Migrate existing projects

```bash
aimake init --from=makefile
aimake init --from=dvc
aimake init --from=prefect
aimake init --from=airflow-dag
```

### Watch mode

```bash
aimake watch              # re-plan on file changes
aimake watch --build      # auto-rebuild stale steps
```

### Documentation website

```bash
cd website
npm install && npm run dev
```

Open http://localhost:3001 — full docs (concepts, CLI, SDKs, Docker, trust, team) with search, sidebar, and dark mode. See [website/README.md](website/README.md).

### Web dashboard

```bash
# Terminal 1 — API
aimake serve --port 8765

# Terminal 2 — Next.js UI
cd dashboard
cp .env.local.example .env.local
npm install && npm run dev
```

Open http://localhost:3000 — graph, builds, experiments, registry, cache, settings, repro, lineage, developer.

### Team & production (v1.5+)

```bash
# Shared S3 cache for CI + laptops
aimake cache remote-init --bucket my-org-cache --team acme
aimake build                      # writes aimake.lock (commit it)
aimake cache pull-lock            # other machine / CI restores pinned fingerprints

# Monorepo
aimake build --project=apps/rag

# Promote with policy gates + remote push
aimake registry promote evaluation v3 --stage production
aimake registry push evaluation v3

# Daily evals
aimake schedule "0 6 * * *"
aimake schedule --job nightly --once

# Notifications / secrets
aimake notify-test --event fail
aimake secrets                    # lists loaded key names only
```

### Trust & correctness (v1.6)

```bash
aimake probe                      # external model drift
aimake repro --format markdown    # fingerprints, git, attestations
aimake lineage --format openlineage --format mlflow
```

```yaml
external:
  - name: llm
    provider: openai
    model: gpt-4o
    revision: "…"
    probe: true
    probe_mode: warn   # or invalidate
validation:
  command: python scripts/check_eval.py
attestation:
  enabled: true
lineage:
  enabled: true
  formats: [openlineage, mlflow]
  auto_export_on_build: true
```

See [CHANGELOG.md](CHANGELOG.md) for full YAML surfaces.

### GitHub Action

```yaml
- uses: arjun988/aimake/.github/actions/aimake@v2
  with:
    config: aimake.yaml
    post-comment: "true"
```

See [docs/COMPARISON.md](docs/COMPARISON.md) and [docs/ADAPTERS.md](docs/ADAPTERS.md).

---

## Example workflow

See [`examples/rag/`](examples/rag/) for a complete RAG pipeline.

```bash
cd examples/rag
aimake build         # first run: all artifacts execute
aimake build         # second run: 0 rebuilt, 7 reused
```

Edit `prompts/system.txt`, then:

```bash
aimake plan          # prompt → evaluation → report marked for rebuild
aimake build         # only downstream artifacts run
aimake explain report
aimake diff prompt
```

---

## How it works

1. **Read** `aimake.yaml` and validate the schema
2. **Construct** a dependency DAG from `depends_on` edges
3. **Fingerprint** each artifact from inputs, dependencies, command, parameters, and environment
4. **Compare** fingerprints against `.aimake/state.db` and `aimake.lock`
5. **Plan** — skip unchanged, restore from cache, or run stale nodes
6. **Execute** commands in topological order (parallel where safe)
7. **Cache** successful outputs content-addressably under `.aimake/cache/`
8. **Record** build metadata, metrics, snapshots, and optional registry entries

Fingerprints use **SHA-256 content hashes**, not timestamps. Changing a file's mtime without changing content does **not** invalidate the cache.

```text
.aimake/
├── state.db          # SQLite: builds, fingerprints, experiments, registry
├── cache/
│   └── <hash>/       # Content-addressable artifact outputs
└── logs/
    └── build-001.log
```

---

## CLI reference

Global options (all commands):

| Option | Description |
|--------|-------------|
| `--version`, `-V` | Print version and exit |
| `--config`, `-c` | Path to `aimake.yaml` (default: project root) |

### Project lifecycle

| Command | Description |
|---------|-------------|
| `aimake init` | Initialize a new project |
| `aimake build [targets...]` | Incremental build |
| `aimake plan [targets...]` | Preview build plan without executing |
| `aimake status [targets...]` | Show artifact status |
| `aimake clean [targets...]` | Remove generated build outputs |
| `aimake doctor` | Project health checks |

**`aimake init`**

```bash
aimake init
aimake init --path ./my-app --name my-rag-app
```

| Option | Description |
|--------|-------------|
| `--path`, `-p` | Project directory (default: cwd) |
| `--name`, `-n` | Project name in `aimake.yaml` |

**`aimake build`**

```bash
aimake build
aimake build evaluation report
aimake build --force
aimake build evaluation --force
aimake build --dry-run
aimake build --jobs 4
aimake build -v --debug
```

| Option | Description |
|--------|-------------|
| `--force`, `-f` | Force rebuild (all targets, or named targets only) |
| `--dry-run`, `-n` | Show plan without executing |
| `--jobs`, `-j` | Parallel jobs (`0` = auto) |
| `--verbose`, `-v` | Verbose output |
| `--debug` | Debug fingerprinting |

**`aimake clean`**

```bash
aimake clean
aimake clean embeddings index
aimake clean --all          # also clear local cache
```

| Option | Description |
|--------|-------------|
| `--all` | Clear `.aimake/cache/` in addition to build outputs |

### Inspection & debugging

| Command | Description |
|---------|-------------|
| `aimake graph` | Display dependency DAG |
| `aimake inspect <artifact>` | Detailed artifact info |
| `aimake explain <target>` | Why is this target stale? |
| `aimake history` | Previous builds |
| `aimake logs <build-id>` | Logs for a specific build |
| `aimake diff <artifact>` | What changed in an artifact |

**`aimake graph`**

```bash
aimake graph
aimake graph --format ascii    # default
aimake graph --format json
aimake graph --format dot
```

**`aimake history`**

```bash
aimake history
aimake history --limit 50
```

**`aimake diff`**

```bash
aimake diff prompt
aimake diff dataset --baseline lock
aimake diff model --baseline stored
aimake diff embeddings --baseline current
```

| Option | Description |
|--------|-------------|
| `--baseline`, `-b` | `stored` (default), `lock`, or `current` |

### Evaluation & quality gates

```bash
aimake eval --check
```

Validates metrics from the latest build against `quality_gates` in `aimake.yaml`. Exits non-zero on failure — ideal for CI.

### Remote cache

```bash
aimake cache status
aimake cache remote-init --bucket my-cache --team acme --region us-east-1
aimake cache push
aimake cache pull
aimake cache pull-lock          # restore fingerprints from aimake.lock
aimake cache sync
```

Requires `cache.remote` in config and `pip install aimake[s3]`. Set `team_id` so CI and laptops share one prefix; commit `aimake.lock` after green builds.

### GPU & distributed workers

```bash
aimake workers
```

Shows local GPU pool and SSH worker availability (see [GPU scheduling](#gpu-scheduling--workers)).

### Experiments

```bash
aimake compare                    # previous vs latest build
aimake compare 3 5                # build #3 vs #5
aimake compare latest previous
aimake optimize                   # run hyperparameter search
aimake optimize --dry-run
aimake optimize -n 20 --name tuning-v2
aimake experiments list
aimake experiments show 1
```

| Command | Options |
|---------|---------|
| `optimize` | `--trials`, `-n`; `--dry-run`; `--name` |
| `experiments list` | `--limit`, `-n` |

### Artifact registry

```bash
aimake registry list
aimake registry list --artifact evaluation --stage production
aimake registry list --tag best
aimake registry show evaluation v1
aimake registry promote evaluation v1 --stage production
aimake registry promote evaluation v1 --stage production --force   # skip policy
aimake registry push evaluation v1
aimake registry tag evaluation v1 best champion
```

Requires `registry.enabled: true` in `aimake.yaml`. Optional `registry.remote` + `policy.promote` for remote push and gates.

| Command | Options |
|---------|---------|
| `registry list` | `--artifact`, `-a`; `--stage`, `-s`; `--tag`, `-t`; `--limit`, `-n` |
| `registry promote` | `--stage`, `-s`; `--force`; `--no-push` |
| `registry push` | push current version to S3 / HF / W&B |

### Plugins

```bash
aimake plugins

# Hugging Face
aimake hf pull <artifact>
aimake hf push <artifact>
aimake hf status [artifact]

# Weights & Biases
aimake wandb sync <artifact>
aimake wandb status [artifact]

# DVC
aimake dvc pull <artifact>
aimake dvc push <artifact>
aimake dvc status [artifact]

# Docker
aimake docker build <artifact>
aimake docker status [artifact]

# Ollama
aimake ollama pull <artifact>
aimake ollama status [artifact]
```

Enable plugins in `aimake.yaml` under `plugins.*.enabled: true`. See [plugin sections](#hugging-face-plugin) below.

### Command summary

```text
aimake
├── init
├── build
├── plan
├── status
├── graph
├── clean
├── history
├── inspect
├── explain
├── doctor
├── eval
├── logs
├── diff
├── workers
├── compare
├── optimize
├── plugins
├── cache
│   ├── status
│   ├── push
│   ├── pull
│   └── sync
├── experiments
│   ├── list
│   └── show
├── registry
│   ├── list
│   ├── show
│   ├── promote
│   └── tag
└── hf
    ├── pull
    ├── push
    └── status
├── wandb
│   ├── sync
│   └── status
├── dvc
│   ├── pull
│   ├── push
│   └── status
├── docker
│   ├── build
│   └── status
└── ollama
    ├── pull
    └── status
```

---

## Configuration

Create `aimake.yaml` in your project root:

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

### Input tracking

```yaml
inputs:
  - data/train.jsonl
  - prompts/system.txt
  - data/**          # glob patterns supported
```

### Environment variables

```yaml
environment:
  - MODEL_NAME
  - API_VERSION
```

Environment variable **names** participate in fingerprints by default (`environment_mode: names`). Use `environment_mode: values` when env values should invalidate the cache. Exclude volatile vars with `volatile_environment`.

### External dependencies (remote models/APIs)

Pin provider/model revisions so a changed API behind the same name invalidates downstream artifacts:

```yaml
artifacts:
  embeddings:
    external:
      - name: openai-embeddings
        provider: openai
        model: text-embedding-3-small
        revision: "2024-01"   # bump when the remote model changes
```

Mark dependencies you accept as nondeterministic with `volatile: true` (excluded from fingerprints).

### Atomic outputs & validation

Failed runs discard partial outputs. Successful runs validate content before caching:

```yaml
project:
  atomic_outputs: true

artifacts:
  evaluation:
    validation:
      non_empty: true
      min_size_bytes: 10
      required_keys: [accuracy, cost_usd]
      min_value:
        accuracy: 0.01
      revalidate_on_cache_hit: true
    cost_estimate:
      cost_usd: 0.42
      tokens: 1200
```

Scripts can write to staged paths with `from aimake.utils.outputs import resolve_output`.

`aimake plan` shows estimated **cost** and **tokens** for steps that will rebuild.

Quality gates support `required: true` to fail when metrics are missing.

### Artifact types

| Type | Description |
|------|-------------|
| `dataset` | Training/evaluation data |
| `model` | Model weights or configuration |
| `prompt` | Prompt templates |
| `embedding` | Vector embeddings |
| `vector_index` | Search indexes |
| `evaluation` | Evaluation runs and metrics |
| `report` | Generated reports |
| `generic` | Any other artifact |

Each artifact supports: `name`, `type`, `depends_on`, `inputs`, `outputs`, `command`, `source`, `environment`, `parameters`, `metadata`, `resources`, `worker`.

---

## Remote cache (S3)

```yaml
cache:
  remote:
    type: s3
    auto_pull: true
    auto_push: true
    s3:
      bucket: my-aimake-cache
      prefix: projects/my-rag-app/
      region: us-east-1
      # endpoint_url: https://minio.example.com  # S3-compatible
```

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
pip install aimake[s3]

aimake cache status
aimake cache push
aimake cache pull
aimake cache sync
```

On build, `auto_pull` restores missing entries from S3; `auto_push` uploads after successful builds.

---

## GPU scheduling & workers

```yaml
project:
  gpus: 2          # local GPUs (0 = auto-detect)

artifacts:
  embeddings:
    type: embedding
    resources:
      gpu: 1
    command: python src/embed.py
    outputs:
      - build/embeddings/

workers:
  enabled: true
  workers:
    - name: gpu-node-1
      host: 10.0.0.5
      user: build
      gpus: 2
      jobs: 2
      workdir: /home/build/my-rag-app

artifacts:
  embeddings:
    worker: gpu-node-1
    resources:
      gpu: 1
```

```bash
aimake workers
```

---

## Artifact diffs

Compare what changed between builds using stored snapshots:

```bash
aimake diff prompt
aimake diff dataset --baseline lock
aimake diff model --baseline stored
```

Shows fingerprint changes, dataset stats, model parameters, and unified prompt diffs.

---

## Experiments & optimization

### Compare builds

```bash
aimake compare
aimake compare 3 5
```

### Hyperparameter search

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

```bash
aimake optimize
aimake optimize --dry-run
aimake optimize -n 10 --name sweep-1
aimake experiments list
aimake experiments show 1
```

Trial parameters are injected as `AIMAKE_PARAM_*` environment variables:

```python
import os
temperature = float(os.environ.get("AIMAKE_PARAM_TEMPERATURE", "1.0"))
```

### Advanced strategies

```yaml
optimization:
  strategy: optuna        # requires pip install aimake[optuna]
  trials: 20
  seed: 42
  early_stopping:
    enabled: true
    patience: 5
    min_trials: 10
    min_delta: 0.001
  mlflow:                 # requires pip install aimake[mlflow]
    enabled: true
    tracking_uri: http://localhost:5000
    experiment_name: my-rag-tuning
  objective:
    metrics: [accuracy, cost_usd]
    directions: [maximize, minimize]
    artifact: evaluation
```

### Hyperband pruning & multi-fidelity

```yaml
optimization:
  strategy: optuna
  pruning:
    enabled: true
    strategy: hyperband       # hyperband | successive_halving
    min_fidelity: 1
    max_fidelity: 3
    reduction_factor: 3
    fidelity_param: epochs
    fidelity_values: [1, 5, 10]
```

Scripts read `AIMAKE_FIDELITY`, `AIMAKE_FIDELITY_VALUE`, and `AIMAKE_MAX_FIDELITY` from the environment.

---

## Artifact registry

```yaml
registry:
  enabled: true
  auto_register: true
  default_stage: dev
```

```bash
aimake registry list
aimake registry show evaluation v1
aimake registry promote evaluation v1 --stage production
aimake registry tag evaluation v1 best
```

---

## Hugging Face plugin

```yaml
plugins:
  huggingface:
    enabled: true
    token_env: HF_TOKEN
    auto_pull: true
    auto_push: false

artifacts:
  embedder:
    type: model
    source: models/embedder
    metadata:
      huggingface:
        repo_id: sentence-transformers/all-MiniLM-L6-v2
        revision: main
        repo_type: model
        pull: true
```

```bash
pip install aimake[huggingface]
aimake hf pull embedder
aimake hf push embedder
aimake hf status
aimake plugins
```

---

## Weights & Biases plugin

```yaml
plugins:
  wandb:
    enabled: true
    entity: my-team
    project: my-rag-app
    api_key_env: WANDB_API_KEY
    auto_log_metrics: true
    auto_log_artifacts: false

artifacts:
  evaluation:
    type: evaluation
    depends_on: [embeddings, prompt]
    command: python src/evaluate.py
    outputs:
      - build/evaluation/
    metrics:
      file: build/evaluation/results.json
    metadata:
      wandb:
        log_metrics: true
        log_artifacts: true
        artifact_name: evaluation-results
```

```bash
pip install aimake[wandb]
export WANDB_API_KEY=...
aimake wandb sync evaluation
aimake wandb status
```

Metrics are logged automatically after each successful build when `auto_log_metrics: true`. Build summaries are logged on `on_build_finish`.

---

## DVC plugin

```yaml
plugins:
  dvc:
    enabled: true
    remote: origin
    auto_pull: true
    auto_push: false

artifacts:
  dataset:
    type: dataset
    source: data/train
    metadata:
      dvc:
        tracked: true
        path: data/train.dvc
        pull: true
```

```bash
pip install aimake[dvc]    # or install dvc CLI separately
aimake dvc pull dataset
aimake dvc push dataset
aimake dvc status
```

DVC data is pulled before builds when local files are missing, and optionally pushed after successful artifact completion.

---

## Docker plugin

```yaml
plugins:
  docker:
    enabled: true
    default_image: python:3.11-slim
    auto_build: true
    gpu: false

artifacts:
  embeddings:
    type: embedding
    depends_on: [processed]
    command: python src/embed.py
    outputs:
      - build/embeddings/
    metadata:
      docker:
        image: my-rag:latest
        dockerfile: docker/Dockerfile
        build_context: .
        workdir: /workspace
        volumes:
          - .:/workspace
        gpu: true
```

```bash
# Requires Docker CLI (Docker Desktop)
aimake docker build embeddings
aimake docker status
aimake build embeddings   # commands run inside docker run ...
```

When `metadata.docker` is set, artifact commands are wrapped in `docker run` automatically during `aimake build`.

---

## Ollama plugin

```yaml
plugins:
  ollama:
    enabled: true
    host: http://localhost:11434
    auto_pull: true

artifacts:
  llm:
    type: model
    source: models/llm
    metadata:
      ollama:
        model: llama3.2
        tag: latest
        pull: true
```

```bash
# Requires Ollama running locally
aimake ollama pull llm
aimake ollama status
aimake build llm
```

Models are pulled via `ollama pull` (or the Ollama HTTP API) before builds when not present locally.

---

## Python API

```python
from aimake.sdk import Aimake

with Aimake.load("aimake.yaml") as ai:
    plan = ai.plan()
    result = ai.build()
    explanation = ai.explain("evaluation")

# Classic Project API still works
from aimake import Project

project = Project.load("aimake.yaml")
project.build()
project.close()
```

TypeScript client (talks to `aimake serve`): see [`sdk/typescript`](sdk/typescript) and [docs/SDK.md](docs/SDK.md).

### Interactive TUI

```bash
aimake tui
```

### Docker

```bash
docker pull ghcr.io/arjun988/aimake:latest
docker run --rm -v "$PWD:/workspace" -w /workspace ghcr.io/arjun988/aimake:latest build
```

---

## CI/CD

```yaml
name: AI Build

on: [push, pull_request]

jobs:
  aimake:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install aimake
      - run: aimake doctor
      - run: aimake build
      - run: aimake eval --check
```

See [`.github/workflows/ci.yml`](.github/workflows/ci.yml) for the full workflow.

---

## Architecture

```text
aimake/
├── cli.py              # Typer CLI
├── project.py          # Python API
├── config/             # YAML schema, loader, validation
├── graph/              # DAG, topological sort, planner
├── hashing/            # SHA-256 fingerprints, file-hash cache
├── cache/              # Local + S3 remote cache
├── scheduling/         # GPU pool, distributed workers
├── diff/               # Dataset/model/prompt diffs + snapshots
├── experiments/        # Compare, optimize, Hyperband, Pareto, MLflow
├── registry/           # Versioned artifact registry
├── plugins/            # HF, W&B, DVC, Docker, Ollama plugins
├── execution/          # Subprocess runner, parallel scheduler
├── artifacts/          # Type-specific artifact handlers
├── metrics/            # Metrics parsing, quality gates
├── git/                # Git metadata integration
├── state/              # SQLite state database
└── ui/                 # Rich terminal output
```

---

## Development

```bash
git clone https://github.com/arjun988/aimake
cd aimake
pip install -e ".[all]"
pytest tests/ -v
```

See [CHANGELOG.md](CHANGELOG.md) for release history.

---

## Security

`aimake.yaml` contains **executable commands** that run on your machine. Review configuration before building, especially from untrusted sources. Secret environment variables are redacted from logs. No remote code execution or automatic configuration loading occurs.

---

## Roadmap

| Status | Item |
|--------|------|
| ✅ | Core incremental builds, fingerprinting, parallel execution |
| ✅ | S3 remote cache, GPU scheduling, distributed workers |
| ✅ | Artifact diffs, experiments, registry, plugins |
| ✅ | Web dashboard + `aimake serve` |
| ✅ | Team features, trust (attest/repro/lineage), Docker, TUI, SDKs |
| 🔜 | Jupyter magic, plugin entry points, doctor --fix |

---

## Contributing

Contributions are welcome! Please open an issue or pull request on [GitHub](https://github.com/arjun988/aimake).

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
