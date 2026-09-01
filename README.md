<div align="center">

# aimake

**The incremental build system for AI applications.**

[![PyPI version](https://img.shields.io/pypi/v/aimake.svg)](https://pypi.org/project/aimake/)
[![Python](https://img.shields.io/pypi/pyversions/aimake.svg)](https://pypi.org/project/aimake/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![CI](https://github.com/aimake/aimake/actions/workflows/ci.yml/badge.svg)](https://github.com/aimake/aimake/actions/workflows/ci.yml)

*Like `make` + `git` + DVC — but designed for AI/ML pipelines.*

[Installation](#installation) · [Quick Start](#quick-start) · [CLI Reference](#cli-reference) · [Configuration](#configuration) · [Examples](examples/rag/)

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
| **Integrations** | MLflow export, Hugging Face Hub, artifact registry with promotion stages |
| **CI** | Quality gates, `doctor` health checks, `eval --check` for pipelines |

---

## Installation

```bash
pip install aimake
```

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
aimake cache push
aimake cache push <fingerprint>
aimake cache pull
aimake cache pull <fingerprint>
aimake cache sync
```

Requires `cache.remote` in config and `pip install aimake[s3]`.

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
aimake registry tag evaluation v1 best champion
```

Requires `registry.enabled: true` in `aimake.yaml`.

| Command | Options |
|---------|---------|
| `registry list` | `--artifact`, `-a`; `--stage`, `-s`; `--tag`, `-t`; `--limit`, `-n` |
| `registry promote` | `--stage`, `-s` (default: `production`) |

### Plugins & Hugging Face

```bash
aimake plugins
aimake hf pull <artifact>
aimake hf push <artifact>
aimake hf status
aimake hf status <artifact>
```

Requires `plugins.huggingface.enabled: true` and `pip install aimake[huggingface]`.

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

Environment variable **names** participate in fingerprints. Secret values are redacted in logs and metadata.

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

## Python API

```python
from aimake import Project

project = Project.load("aimake.yaml")

plan = project.plan()
result = project.build()
explanation = project.explain("evaluation")
diff = project.diff("prompt")
comparison = project.compare_builds("previous", "latest")

project.close()
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
├── plugins/            # Hugging Face and extensible plugin loader
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
git clone https://github.com/aimake/aimake
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
| ✅ | Artifact diffs, experiment comparison, hyperparameter optimization |
| ✅ | Bayesian/Optuna, Pareto, MLflow, early stopping, Hyperband pruning |
| ✅ | Artifact registry, Hugging Face plugin |
| 🔜 | Web dashboard |
| 🔜 | Weights & Biases, DVC, Docker, Ollama plugins |

---

## Contributing

Contributions are welcome! Please open an issue or pull request on [GitHub](https://github.com/aimake/aimake).

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
