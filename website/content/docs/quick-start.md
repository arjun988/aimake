---
title: Quick start
description: Scaffold a project, run plan and build, try the RAG example, and explore watch, dashboard, and team workflows.
---

## Five-minute path

```bash
pip install aimake
aimake init          # scaffold aimake.yaml + .aimake/
aimake plan          # preview what will run
aimake build         # incremental build
aimake status        # artifact freshness
aimake graph         # dependency DAG
```

That is enough to confirm the CLI works. The rest of this page walks through a real pipeline and the daily commands you will use most.

## Initialize a project

```bash
aimake init
aimake init --path ./my-app --name my-rag-app
```

| Option | Description |
|--------|-------------|
| `--path`, `-p` | Project directory (default: current working directory) |
| `--name`, `-n` | Project name written into `aimake.yaml` |

`init` creates:

- `aimake.yaml` — artifact DAG and settings
- `.aimake/` — local state database, cache, and logs

### Migrate instead of starting blank

If you already have Make, DVC, Prefect, or Airflow:

```bash
aimake init --from=makefile
aimake init --from=dvc
aimake init --from=prefect
aimake init --from=airflow-dag
```

Review the generated YAML before production use. Full guide: [Migration](/docs/migration).

## Run the RAG example

The canonical sample lives at [`examples/rag/`](https://github.com/arjun988/aimake/tree/main/examples/rag):

```bash
# from a clone of the aimake repo
cd examples/rag
aimake build         # first run: all artifacts execute
aimake build         # second run: 0 rebuilt, reused from cache
```

The example declares seven artifacts: `dataset` → `preprocess` → `embeddings` → `index`, plus `prompt`, then `evaluation` → `report`.

### See incremental rebuilds

Edit `prompts/system.txt`, then:

```bash
aimake plan          # prompt → evaluation → report marked for rebuild
aimake build         # only downstream artifacts run
aimake explain report
aimake diff prompt
```

Upstream embeddings and the vector index stay cached because their content fingerprints did not change.

## Everyday commands

### Plan before you spend

```bash
aimake plan
aimake plan evaluation report
```

`plan` shows skip / restore / run actions and estimated **cost** / **tokens** when artifacts declare `cost_estimate`. Prefer plan in CI and before expensive evals.

### Build targets

```bash
aimake build
aimake build evaluation report
aimake build --force
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

### Inspect the graph

```bash
aimake status
aimake graph
aimake graph --format ascii
aimake graph --format json
aimake graph --format dot
aimake inspect evaluation
aimake explain evaluation
aimake explain evaluation --tree
```

### Clean outputs

```bash
aimake clean
aimake clean embeddings index
aimake clean --all          # also clear local cache
```

## Watch mode

Rebuild as you edit sources:

```bash
aimake watch              # re-plan on file changes
aimake watch --build      # auto-rebuild stale steps
```

## Web dashboard

```bash
# Terminal 1 — API
aimake serve --port 8765

# Terminal 2 — Next.js UI (from the aimake repo)
cd dashboard
cp .env.local.example .env.local
npm install && npm run dev
```

Open http://localhost:3000 for graph, builds, experiments, registry, cache, settings, repro, lineage, and developer views.

You can also start the API via `aimake graph --serve`. See [Dashboard](/docs/dashboard).

## Interactive TUI

```bash
aimake tui
```

Rich full-screen plan / build / metrics — useful when you want more than streaming logs. See [Interactive TUI](/docs/tui).

## Quality gates

After a successful build:

```bash
aimake eval --check
```

This validates metrics from the latest build against `quality_gates` in `aimake.yaml` and exits non-zero on failure — ideal for CI. See [CI/CD](/docs/ci-cd).

## Team & production (v1.5+)

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

More: [Remote & team cache](/docs/remote-cache), [Team & production](/docs/team), [Artifact registry](/docs/registry).

## Trust & correctness (v1.6+)

```bash
aimake probe                      # external model drift
aimake repro --format markdown    # fingerprints, git, attestations
aimake lineage --format openlineage --format mlflow
```

Example YAML surfaces:

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

See [Trust & reproducibility](/docs/trust).

## Python one-liner

```python
from aimake.sdk import Aimake

with Aimake.load("aimake.yaml") as ai:
    plan = ai.plan()
    result = ai.build()
    explanation = ai.explain("evaluation")
```

SDK docs: [Python SDK](/docs/sdk-python).

## What to read next

| Goal | Page |
|------|------|
| Understand fingerprints and the DAG | [Core concepts](/docs/concepts) |
| Declare artifacts correctly | [Writing aimake.yaml](/docs/configuration) |
| Cache hits, misses, remote sync | [Fingerprints & caching](/docs/caching) |
| Wire GitHub Actions | [CI/CD](/docs/ci-cd) |
| Full command list | [CLI reference](/docs/cli) |
