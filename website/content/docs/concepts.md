---
title: Core concepts
description: Artifacts, dependency DAGs, fingerprints, plans, locks, caches, and quality gates — the building blocks of aimake.
---

## Overview

aimake models an AI pipeline as a **directed acyclic graph (DAG)** of **artifacts**. Each artifact has a **fingerprint** derived from content and configuration. A **plan** decides whether to skip, restore from cache, or run each node. Successful runs update **state**, **cache**, and optionally **`aimake.lock`**.

Understanding these concepts makes every CLI command predictable.

## Artifacts

An artifact is a named node in `aimake.yaml`. It is usually either:

- a **source** artifact (`source:` path) — data or prompts you author, or
- a **command** artifact (`command:` + `outputs:`) — something you build.

```yaml
artifacts:
  dataset:
    type: dataset
    source: data/train.jsonl

  embeddings:
    type: embedding
    depends_on: [processed]
    command: python src/embed.py
    outputs:
      - build/embeddings/
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

Common fields: `name`, `type`, `depends_on`, `inputs`, `outputs`, `command`, `source`, `environment`, `parameters`, `metadata`, `resources`, `worker`, `metrics`, `external`, `validation`, `cost_estimate`.

Full schema walkthrough: [Writing aimake.yaml](/docs/configuration).

## Dependency DAG

Edges come from `depends_on`. aimake topologically sorts the graph so parents finish before children. Independent branches can run in parallel (`aimake build --jobs N`).

```text
dataset → preprocess → embeddings → index ─┐
prompt ────────────────────────────────────┴─► evaluation → report
```

Commands that visualize this:

```bash
aimake graph
aimake graph --format dot
```

Cycles are rejected at load time — the graph must stay acyclic.

## Fingerprints

A fingerprint is a **SHA-256** digest over the inputs that should invalidate an artifact when they change. That typically includes:

- Content of `source` / tracked `inputs` (and globs)
- Fingerprints of upstream dependencies
- The `command` string
- Declared `parameters`
- Environment **names** (default) or **values** (optional mode)
- External model pins (`external.revision`, provider, model)

**Not** used: file modification time alone. Changing mtime without changing content does not bust the cache.

```bash
aimake inspect embeddings
aimake diff prompt
aimake explain evaluation --tree
```

Deep dive: [Fingerprints & caching](/docs/caching) and [How aimake works](/docs/how-it-works).

## Plans

`aimake plan` (and the planning phase of `aimake build`) classifies each artifact:

| Action | Meaning |
|--------|---------|
| **skip** / reuse | Fingerprint matches last successful build; outputs present |
| **restore** | Cache hit for the fingerprint, but outputs missing locally — copy from cache |
| **run** | Stale or never built — execute `command` |

Plans can surface estimated **cost_usd** and **tokens** from `cost_estimate` on artifacts that will run — so you see the bill before you pay.

```bash
aimake plan
aimake plan --format json
```

## State database

Local metadata lives under `.aimake/`:

```text
.aimake/
├── state.db          # SQLite: builds, fingerprints, experiments, registry
├── cache/
│   └── <hash>/       # Content-addressable artifact outputs
├── logs/
│   └── build-001.log
└── attestations/     # optional SLSA-lite provenance
```

`state.db` remembers what ran, when, with which fingerprints, and stores experiment / registry records. You normally do not edit it by hand.

## Content-addressable cache

After a successful run, outputs are stored under `.aimake/cache/<fingerprint>/`. Later builds with the same fingerprint can **restore** instead of re-executing expensive work.

Optional S3 remote cache shares those entries across laptops and CI:

```bash
aimake cache status
aimake cache push
aimake cache pull
aimake cache sync
```

See [Remote & team cache](/docs/remote-cache).

## Lock files

`aimake.lock` pins fingerprints after green builds. Commit it so teammates and CI agree on what “good” looked like.

```bash
aimake build
aimake cache pull-lock    # restore pinned fingerprints on another machine
```

With `team_id` and remote cache (v1.5+), lock v2 also pins remote identity so shared prefixes stay consistent.

## Metrics and quality gates

Evaluation artifacts can declare a metrics file:

```yaml
evaluation:
  type: evaluation
  depends_on: [index, prompt]
  command: python src/evaluate.py
  outputs:
    - build/evaluation/
  metrics:
    file: build/evaluation/results.json
```

Project-level gates fail CI when thresholds are missed:

```yaml
quality_gates:
  accuracy:
    minimum: 0.80
    required: true
  cost_usd:
    maximum: 1.00
    required: true
```

```bash
aimake eval --check
```

## External dependencies

Remote models and APIs do not live on disk. Pin them so a silent provider change invalidates downstream work:

```yaml
external:
  - name: openai-embeddings
    provider: openai
    model: text-embedding-3-small
    revision: "2024-01"
    probe: true
    probe_mode: warn   # or invalidate
```

`aimake probe` checks for drift. Mark intentional nondeterminism with `volatile: true` (excluded from fingerprints).

## Validation and atomic outputs

Failed runs discard partial outputs when `atomic_outputs` is enabled. Successful runs can validate structure before caching:

```yaml
validation:
  non_empty: true
  min_size_bytes: 10
  required_keys: [accuracy, cost_usd]
  command: python scripts/check_eval.py
```

## Experiments and registry

- **Experiments** — `aimake optimize` sweeps parameters; trials inject `AIMAKE_PARAM_*` env vars. See [Experiments](/docs/experiments).
- **Registry** — version and promote artifacts (`dev` → `production`) with optional policy gates. See [Artifact registry](/docs/registry).

## Putting it together

1. Author artifacts and edges in YAML.
2. `plan` to see cost and rebuild scope.
3. `build` to execute and cache.
4. `explain` / `diff` when results surprise you.
5. `eval --check` (and optionally registry promote) to ship.

Next: [How aimake works](/docs/how-it-works) for the step-by-step engine pipeline.
