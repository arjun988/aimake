---
title: Python SDK
description: Use Aimake.load(), the Project API, and common methods from Python scripts and CI — in-process incremental builds.
---

Drive aimake from Python scripts, notebooks (via subprocess/CLI), or CI without shelling out for every call. The stable import surface is `aimake.sdk` (and `aimake.Project`).

Requires Python **3.11+** and `pip install aimake`.

Related: [TypeScript SDK](/docs/sdk-typescript) (HTTP client for `aimake serve`), [Docker](/docs/docker), [CLI reference](/docs/cli).

---

## Quick start

```python
from aimake.sdk import Aimake, load

# Context-manager style (recommended for CI)
with Aimake.load("aimake.yaml") as ai:
    plan = ai.plan()
    print(plan.to_run, plan.estimated_total_cost_usd)
    result = ai.build()
    assert result.success, result.failed
```

`Aimake` is a thin ergonomic wrapper around `Project`. Prefer `with Aimake.load(...)` so SQLite state is closed cleanly.

---

## Aimake.load() and load()

```python
from aimake.sdk import Aimake, load

# Path to yaml or directory containing aimake.yaml
ai = Aimake.load("aimake.yaml")
ai = Aimake.load(".")           # resolves ./aimake.yaml
ai = Aimake.load(debug=True)    # cwd project

# Monorepo shorthand → apps/rag/aimake.yaml
ai = Aimake.load(project="apps/rag")

# Same resolution without the wrapper
proj = load("aimake.yaml")
proj = load(project="apps/rag", verbose=True)
```

Do not pass both `path` and `project`.

---

## Classic Project API

```python
from aimake import Project

project = Project.load("aimake.yaml")
project.build(targets=["evaluation"], jobs=4)
project.explain("evaluation", tree=True)
project.close()
```

Or via the wrapper’s `.project` property:

```python
with Aimake.load() as ai:
    ai.project.compare_builds(12, 15)
    ai.project.repro_report(fmt="markdown")
```

---

## Common methods

### On `Aimake` (wrapper)

| Method | Purpose |
|--------|---------|
| `Aimake.load(path=None, *, project=None, debug=False, verbose=False)` | Construct wrapper |
| `plan(targets=None, **kwargs)` | What would run / restore / skip (+ cost estimates) |
| `build(targets=None, force=..., dry_run=..., jobs=...)` | Execute incremental build |
| `status(targets=None)` | Per-artifact status map |
| `explain(name, **kwargs)` | Why an artifact is stale (`tree=True` supported via Project) |
| `doctor()` | Health checks (list of issue/OK strings) |
| `close()` / context manager | Release `state.db` |

### On `Project` (full API)

| Method | Purpose |
|--------|---------|
| `plan` / `build` / `status` / `explain` / `doctor` | Same as above |
| `compare_builds(a, b)` | Metric deltas between build IDs |
| `registry_list` / `registry_promote` / `registry_tag` / `registry_push` | Versioned registry (+ [policy gates](/docs/security)) |
| `policy_check_promote(...)` | Preview promote violations |
| `probe_external_drift()` | External model drift probes |
| `repro_report(fmt="markdown")` | Reproducibility report path |
| `export_lineage(...)` | OpenLineage / MLflow / W&B JSON |
| `lineage_graph()` | Graph dict for dashboards |
| `list_attestations()` | SLSA-lite sidecars under `.aimake/attestations/` |

Return types live in `aimake.models` (`BuildPlan`, `BuildResult`, `ExplainResult`, `ArtifactStatus`, …) and are re-exported from `aimake.sdk`.

---

## Build plan fields

```python
plan = ai.plan(targets=["evaluation"])
plan.to_run       # stale / missing — will execute
plan.to_skip      # fingerprint match
plan.to_restore   # cache hit, materialize outputs
plan.estimated_total_cost_usd
plan.estimated_total_tokens
plan.entries      # per-artifact action, reason, cost
```

Use this before spending on LLM/eval steps — same data as `aimake plan` and the [dashboard](/docs/dashboard).

---

## Monorepo

```python
from aimake.sdk import load

proj = load(project="apps/rag")
proj.build()
```

Equivalent CLI: `aimake build --project=apps/rag` / `-P`. See [Team & production](/docs/team).

---

## Example CI snippet

```python
# scripts/ci_build.py
from aimake.sdk import Aimake

with Aimake.load() as ai:
    issues = ai.doctor()
    # fail on unexpected doctor errors as you prefer
    plan = ai.plan()
    if plan.estimated_total_cost_usd > 5.0:
        raise SystemExit(f"plan too expensive: ${plan.estimated_total_cost_usd}")
    result = ai.build(jobs=4)
    raise SystemExit(0 if result.success else 1)
```

For containerized CI without installing Python deps in the job image, see [Docker](/docs/docker). For a JS/TS control plane over the same project, start `aimake serve` and use the [TypeScript SDK](/docs/sdk-typescript).
