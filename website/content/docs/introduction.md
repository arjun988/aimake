---
title: Introduction
description: What aimake is, why AI pipelines need incremental builds, and how it fits next to Make, DVC, and orchestrators.
---

## What is aimake?

**aimake** is an incremental build system for AI and ML pipelines. It sits in the same mental model as `make`, `git`, and DVC — but it is shaped for the artifacts AI teams actually touch: datasets, prompts, embeddings, indexes, models, evaluations, and reports.

Install from [PyPI](https://pypi.org/project/aimake/) (`pip install aimake`). Source and issues live on [GitHub](https://github.com/arjun988/aimake). Current stable line is **v2.0**.

When only a prompt changes, everything upstream should be skipped. aimake tracks a dependency DAG, fingerprints inputs with **SHA-256 content hashes** (not file mtimes), and rebuilds only the nodes that actually changed — locally, in CI, or across a shared remote cache.

## Why traditional tools fall short

Classic build tools understand `source → object → binary`. AI pipelines look different:

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

| Tool | Focus |
|------|-------|
| **Make** | Generic file dependencies (mtime-based) |
| **DVC** | Data and model versioning |
| **MLflow** | Experiment tracking |
| **Prefect / Airflow** | Scheduling and orchestration at scale |
| **aimake** | Incremental AI pipeline builds with content-addressable caching |

aimake does not try to replace orchestrators or data registries. It answers a narrower question: *given this DAG of AI artifacts, what must run again, what can be restored from cache, and what will it cost?*

See the full comparison in [Comparison](/docs/comparison).

## What you get

| Category | Capabilities |
|----------|-------------|
| **Core** | Dependency DAG, SHA-256 fingerprinting, parallel builds, content-addressable cache |
| **CLI** | 25+ commands for build, plan, inspect, explain, diff, compare, optimize, registry |
| **Cache** | Local SQLite + filesystem; optional S3 remote (`push` / `pull` / `sync`) |
| **Compute** | GPU-aware scheduling, distributed SSH workers |
| **Experiments** | Grid / random / Bayesian / Optuna search, Hyperband pruning, Pareto multi-objective |
| **Integrations** | MLflow, Hugging Face Hub, W&B, DVC, Docker, Ollama, artifact registry |
| **CI** | Quality gates, `doctor` health checks, official GitHub Action, `eval --check` |
| **Team** | Shared remote cache, `aimake.lock`, registry promote policies, schedules, notifications |
| **Trust** | External probes, attestation, reproducibility reports, lineage export |

## The mental model in one minute

1. You declare artifacts in `aimake.yaml` — each with `depends_on`, `command`, `outputs`, and optional `metrics`, `external`, and `validation`.
2. `aimake plan` shows which steps will run, restore, or skip — including estimated **cost** and **tokens** when you provide them.
3. `aimake build` executes only stale work in topological order (parallel where safe).
4. Successful outputs land in a content-addressable cache under `.aimake/cache/`.
5. `aimake explain` tells you *why* a target is stale when something surprises you.

Fingerprints use content hashes. Touching a file's mtime without changing bytes does **not** invalidate the cache. Details are in [How aimake works](/docs/how-it-works) and [Fingerprints & caching](/docs/caching).

## A concrete example

The sample project at [`examples/rag/`](https://github.com/arjun988/aimake/tree/main/examples/rag) is a complete RAG pipeline:

```bash
cd examples/rag
aimake build         # first run: all artifacts execute
aimake build         # second run: 0 rebuilt, reused from cache
```

Edit `prompts/system.txt`, then:

```bash
aimake plan          # prompt → evaluation → report marked for rebuild
aimake build         # only downstream artifacts run
aimake explain report
aimake diff prompt
```

Upstream steps (`dataset`, `preprocess`, `embeddings`, `index`) stay cached because their fingerprints did not change.

## Who aimake is for

- Teams that change **prompts, models, or configs** often and hate rerunning the whole pipeline
- Engineers who want **`aimake plan`** to show **cost and tokens** before spending API budget
- Pipelines that are **local-first** (laptop + CI) with an optional shared S3 cache
- Projects that need **quality gates** and **output validation** on evaluation artifacts

If you primarily need Git-linked dataset versioning, keep DVC (aimake has a [DVC plugin](/docs/plugins)). If you need cluster-wide scheduling with SLAs, keep Prefect or Airflow and call `aimake build` as one step.

## Next steps

1. [Install aimake](/docs/installation) (Python 3.11+)
2. Follow the [Quick start](/docs/quick-start)
3. Learn [Core concepts](/docs/concepts) — artifacts, fingerprints, plans, locks
4. Migrate an existing project with [Migration](/docs/migration) (`--from=makefile|dvc|prefect|airflow-dag`)
