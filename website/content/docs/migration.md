---
title: Migration
description: Move from Make, DVC, Prefect, or Airflow into aimake with init --from generators, mapping guides, and coexistence patterns.
---

## Overview

aimake complements tools you may already use. Migration is usually **incremental**: generate a starter `aimake.yaml`, map stages to artifacts, keep DVC or an orchestrator where they shine, and let aimake own incremental rebuilds and cost-aware planning.

Generators:

```bash
aimake init --from=makefile
aimake init --from=dvc
aimake init --from=prefect
aimake init --from=airflow-dag
```

Always **review** the generated YAML before production use — generators create a starting DAG, not a finished production policy.

Fresh projects can skip migration:

```bash
aimake init
# or start from examples/rag
```

## Before you migrate

Ask which pain you are solving:

| Pain | aimake answer |
|------|----------------|
| Prompt tweak reruns the whole pipeline | Content fingerprints + selective rebuild |
| CI burns money on unchanged embeddings | Plan + cache + optional S3 remote |
| No single DAG for data → embed → eval → report | `aimake.yaml` artifacts |
| Need quality gates in PRs | `aimake eval --check` |

If you primarily need dataset versioning, keep **DVC**. If you need fleet scheduling and SLAs, keep **Prefect / Airflow** and call `aimake build` inside a flow/task. See [Comparison](/docs/comparison).

## From Make / Makefile

### Generate

```bash
aimake init --from=makefile
```

### Mental mapping

| Make | aimake |
|------|--------|
| Target | Artifact name |
| Prerequisites | `depends_on` |
| Recipe | `command` |
| Target file | `outputs` |
| Source files | `source` / `inputs` |
| mtime invalidation | SHA-256 fingerprints |

### Example translation

Makefile style:

```make
build/embeddings/: build/processed/
	python src/embed.py
```

aimake style:

```yaml
embeddings:
  type: embedding
  depends_on: [processed]
  command: python src/embed.py
  outputs:
    - build/embeddings/
```

### Tips

- Split giant catch-all targets into typed artifacts (`prompt`, `embedding`, `evaluation`).
- Move phony “run everything” targets to `aimake build` (no phony needed).
- Replace `make clean` with `aimake clean` / `aimake clean --all`.

## From DVC

### Generate

```bash
aimake init --from=dvc
```

### Coexistence (recommended)

Keep DVC for **data versioning**; use aimake for **incremental pipeline execution**:

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
pip install "aimake[dvc]"
aimake dvc pull dataset
aimake build
```

### Mapping

| DVC | aimake |
|-----|--------|
| Stage | Artifact |
| `deps` | `depends_on` + `inputs` |
| `outs` | `outputs` |
| `cmd` | `command` |
| Remote storage | DVC remotes **or** aimake S3 cache (different jobs) |

DVC remotes version datasets; aimake’s cache stores build outputs keyed by fingerprints. Many teams use both.

## From Prefect

### Generate

```bash
aimake init --from=prefect
```

### Pattern

Prefect (or any orchestrator) remains the **scheduler**. Each flow run becomes thin:

```python
# Conceptual — keep your Prefect deployment; shell out or call the SDK
from aimake.sdk import Aimake

with Aimake.load("aimake.yaml") as ai:
    ai.build()
```

Or in a Prefect shell task: `aimake build`.

### Mapping

| Prefect | aimake |
|---------|--------|
| Task | Artifact (when it produces files/metrics) |
| Flow dependencies | `depends_on` |
| Retries / schedules | Stay in Prefect (`aimake schedule` is available for simpler cron needs) |
| Result persistence | aimake cache + optional registry |

Avoid duplicating the entire DAG in both systems. Prefer: orchestrator triggers **one** incremental build.

## From Airflow

### Generate

```bash
aimake init --from=airflow-dag
```

### Pattern

Collapse many Airflow operators that only exist for “don’t rerun if inputs unchanged” into a single `BashOperator` / task running `aimake build`. Keep Airflow for dataset sensors, cluster affinity, and SLA emails.

```yaml
# sketch inside your DAG definition's bash command
aimake build --config /opt/airflow/dags/my_app/aimake.yaml
aimake eval --check --config /opt/airflow/dags/my_app/aimake.yaml
```

### Mapping

| Airflow | aimake |
|---------|--------|
| Task / operator | Artifact or whole `aimake build` |
| Upstream tasks | `depends_on` inside YAML |
| XComs for heavy artifacts | Prefer filesystem `outputs` + cache |
| Datasets / sensors | Remain in Airflow; pin paths as `inputs` |

## Greenfield checklist after any `--from`

1. Run `aimake doctor`
2. Open `aimake.yaml` — fix paths, types, and commands
3. Add `metrics` + `quality_gates` on evaluation nodes
4. Add `cost_estimate` on expensive steps
5. Pin `external` models with revisions
6. `aimake plan` then `aimake build`
7. Commit `aimake.lock` once green
8. Wire [CI/CD](/docs/ci-cd)

## Mapping an existing RAG / eval repo by hand

If generators do not fit, model the graph like [`examples/rag`](https://github.com/arjun988/aimake/tree/main/examples/rag):

```text
dataset → preprocess → embeddings → index ─┐
prompt ────────────────────────────────────┴─► evaluation → report
```

```yaml
artifacts:
  dataset:
    type: dataset
    source: data/train.jsonl
  prompt:
    type: prompt
    source: prompts/system.txt
  # ... command artifacts with depends_on / outputs
```

Copy structure from the example, then swap in your scripts.

## Using the Python API during migration

```python
from aimake.sdk import Aimake

with Aimake.load("aimake.yaml") as ai:
    print(ai.plan())
    ai.build()
```

Classic API:

```python
from aimake import Project

project = Project.load("aimake.yaml")
project.build()
project.close()
```

See [Python SDK](/docs/sdk-python).

## Common pitfalls

- **Leaving mtime assumptions in scripts** — aimake will skip based on fingerprints; scripts should be deterministic given inputs.
- **Omitting `outputs`** — the planner and cache need declared paths.
- **Giant monolithic commands** — split so prompt edits do not rebuild embeddings.
- **Unpinned APIs** — add `external.revision` or evals will drift without rebuilds.
- **Expecting aimake to replace DVC remotes** — use the DVC plugin for data; use aimake cache for build products.

## Related pages

- [Introduction](/docs/introduction) — positioning
- [Comparison](/docs/comparison) — feature matrix vs Make / DVC / Prefect / Airflow
- [Quick start](/docs/quick-start) — first successful build
- [Writing aimake.yaml](/docs/configuration) — full schema
- [Adapters](/docs/adapters) — LangChain / LlamaIndex / HF integration notes
