---
title: Plugins overview
description: Enable Hugging Face, Weights & Biases, DVC, Docker, and Ollama integrations in aimake.yaml and use their CLI commands.
---

aimake ships first-party plugins that connect incremental builds to common ML tooling. Plugins are **opt-in**: enable them in `aimake.yaml`, install the matching extra (when needed), then use `aimake <plugin> …` commands or let auto-hooks run during `aimake build`.

| Plugin | Extra | What it does |
|--------|-------|--------------|
| **Hugging Face** | `aimake[huggingface]` | Pull/push Hub models and datasets into artifacts |
| **Weights & Biases** | `aimake[wandb]` | Log metrics and artifacts after successful builds |
| **DVC** | `aimake[dvc]` | Pull/push DVC-tracked data before/after builds |
| **Docker** | Docker CLI | Build images and wrap artifact commands in `docker run` |
| **Ollama** | Ollama local | Pre-pull local LLM models before builds |

List loaded plugins:

```bash
aimake plugins
```

Related: [Adapters](/docs/adapters) for LangChain / LlamaIndex / Transformers pipelines, [Docker image](/docs/docker) for running aimake itself in a container, [Security](/docs/security) for token env vars.

---

## Enable plugins in aimake.yaml

Top-level `plugins` block — each plugin has `enabled: true|false` plus provider-specific options:

```yaml
plugins:
  huggingface:
    enabled: true
    token_env: HF_TOKEN
    auto_pull: true
    auto_push: false

  wandb:
    enabled: true
    entity: my-team
    project: my-rag-app
    api_key_env: WANDB_API_KEY
    auto_log_metrics: true
    auto_log_artifacts: false

  dvc:
    enabled: true
    remote: origin
    auto_pull: true
    auto_push: false

  docker:
    enabled: true
    default_image: python:3.11-slim
    auto_build: true
    gpu: false

  ollama:
    enabled: true
    host: http://localhost:11434
    auto_pull: true
```

Per-artifact settings live under `metadata.<plugin>` on the artifact. Builds call `PluginManager.wrap_command()` (Docker) and may pre-pull DVC data / Ollama models before planning.

---

## Hugging Face

Pull Hub models into a local path, or push trained artifacts back.

```yaml
plugins:
  huggingface:
    enabled: true
    token_env: HF_TOKEN
    auto_pull: true

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
export HF_TOKEN=...   # if the repo is private

aimake hf pull embedder
aimake hf push embedder
aimake hf status
# or status for one artifact:
aimake hf status embedder
```

Use with fine-tune steps that need a GPU — see [GPU & workers](/docs/workers) and the [Adapters](/docs/adapters#hugging-face-transformers) HF section.

---

## Weights & Biases

Log evaluation metrics (and optionally artifacts) to a W&B project.

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
aimake wandb status evaluation
```

When `auto_log_metrics: true`, metrics are logged after each successful artifact build. Build summaries are logged on `on_build_finish`. For experiment tracking comparison, see also [Experiments](/docs/experiments) and lineage export formats that include `wandb` in [Trust & reproducibility](/docs/trust).

---

## DVC

Keep DVC as the data registry; use aimake for incremental AI steps on top.

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
pip install aimake[dvc]    # or install the dvc CLI separately

aimake dvc pull dataset
aimake dvc push dataset
aimake dvc status
```

With `auto_pull: true`, missing local data is pulled **before** the build plan runs. Optional `auto_push` uploads after a successful artifact completion. Migrate an existing DVC pipeline with `aimake init --from=dvc` — see [Migration](/docs/migration) and [Comparison](/docs/comparison).

---

## Docker plugin

Separate from the [official aimake container image](/docs/docker): this plugin runs **your** artifact commands inside images you define.

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
# Requires Docker Desktop / Docker CLI on PATH
aimake docker build embeddings   # build the image from dockerfile
aimake docker status
aimake build embeddings          # command runs via docker run …
```

When `metadata.docker` is set, aimake rewrites the artifact command through `docker run` during `aimake build`. GPU passthrough follows `metadata.docker.gpu` or the plugin default.

---

## Ollama

Ensure local models exist before steps that call Ollama.

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
# Requires Ollama running locally (or reachable at plugins.ollama.host)
aimake ollama pull llm
aimake ollama status
aimake build llm
```

Models are pulled with `ollama pull` (or the HTTP API) when not present locally and `auto_pull` / `metadata.ollama.pull` is enabled.

---

## Install extras

```bash
pip install aimake[huggingface]
pip install aimake[wandb]
pip install aimake[dvc]
pip install aimake[plugins]   # HF + W&B + DVC together
pip install aimake[all]       # all optional features + dev tools
```

Docker and Ollama plugins need the respective CLIs/daemons; they do not add Python package dependencies.

---

## Common command cheat sheet

```text
aimake plugins

aimake hf pull|push|status [artifact]
aimake wandb sync|status [artifact]
aimake dvc pull|push|status [artifact]
aimake docker build|status [artifact]
aimake ollama pull|status [artifact]
```

During a normal build, enabled plugins may:

1. **Pre-pull** DVC data and Ollama models
2. **Wrap** commands in Docker
3. **Post-log** W&B metrics / optionally push HF or DVC

For wiring existing framework code (not Hub sync), continue to [Adapters](/docs/adapters).
