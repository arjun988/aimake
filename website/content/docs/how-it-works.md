---
title: How aimake works
description: End-to-end build pipeline — YAML load, DAG construction, SHA-256 fingerprinting, planning, execution, and caching.
---

## The eight-step pipeline

Every `aimake build` (and the dry preview from `aimake plan`) follows the same engine path:

1. **Read** `aimake.yaml` and validate the schema
2. **Construct** a dependency DAG from `depends_on` edges
3. **Fingerprint** each artifact from inputs, dependencies, command, parameters, and environment
4. **Compare** fingerprints against `.aimake/state.db` and `aimake.lock`
5. **Plan** — skip unchanged, restore from cache, or run stale nodes
6. **Execute** commands in topological order (parallel where safe)
7. **Cache** successful outputs content-addressably under `.aimake/cache/`
8. **Record** build metadata, metrics, snapshots, and optional registry entries

Fingerprints use **SHA-256 content hashes**, not timestamps. Changing a file's mtime without changing content does **not** invalidate the cache.

## Step 1 — Load and validate config

aimake resolves the config path (`aimake.yaml` by default, or `--config` / `-c`). The loader validates project fields, artifact types, dependency references, and plugin / cache / registry blocks. Invalid graphs fail fast with a clear error instead of half-running a build.

Monorepos can point at a subproject:

```bash
aimake build --project=apps/rag
# or -P apps/rag
```

## Step 2 — Build the DAG

Each artifact becomes a node. Each `depends_on` entry becomes a directed edge from dependency → dependent. aimake:

- Detects missing dependency names
- Rejects cycles
- Computes a topological order for execution
- Identifies independent subgraphs eligible for parallelism

```bash
aimake graph --format ascii
aimake graph --format json
```

## Step 3 — Fingerprint artifacts

For each node, the hasher combines:

| Ingredient | Role |
|------------|------|
| Source / input file bytes | Content changes invalidate |
| Upstream fingerprints | Parent changes cascade |
| Command string | Script invocation changes invalidate |
| Parameters | Hyperparams / knobs |
| Environment | Names (default) or values |
| External pins | Provider / model / revision |

Source artifacts without commands are still fingerprinted so dependents see prompt or dataset edits.

Debug fingerprint composition:

```bash
aimake build --debug
aimake inspect <artifact>
```

## Step 4 — Compare to prior state

The planner loads:

- Last known fingerprints from `.aimake/state.db`
- Optional pins from `aimake.lock`
- Presence of declared `outputs` on disk
- Entries in the local (and optionally remote) content-addressable cache

A matching fingerprint with missing outputs is a **restore** candidate, not necessarily a full rebuild (partial restore, v1.6+).

## Step 5 — Produce a plan

```bash
aimake plan
aimake plan evaluation --format json
```

Each entry gets an action (`run`, restore, skip/reuse) plus optional cost estimates from `cost_estimate`:

```yaml
cost_estimate:
  cost_usd: 0.42
  tokens: 1200
```

`aimake plan` aggregates estimated totals so CI and humans can decide whether to proceed.

## Step 6 — Execute

Runner behavior:

- Walk the DAG in topological order
- Skip / restore nodes that do not need work
- Run `command` in a subprocess (or via Docker / remote worker when configured)
- Respect `--jobs` / `-j` for parallel execution of ready nodes
- Apply GPU resource claims (`resources.gpu`) and optional SSH workers

```bash
aimake build --jobs 4
aimake workers          # inspect GPU pool / workers
```

Failed commands fail the build. With `atomic_outputs: true`, partial output directories are discarded so a broken run cannot poison the next cache decision.

Plugins may pull data before execution (DVC, Hugging Face, Ollama) and push or log after success (W&B, HF, DVC).

## Step 7 — Cache outputs

On success, aimake:

1. Runs structural / custom **validation** if configured
2. Stores outputs under `.aimake/cache/<sha256>/`
3. Optionally **auto_push** to S3 remote cache
4. Writes attestation sidecars when `attestation.enabled` is true

Later builds with the same fingerprint restore from local cache, or **auto_pull** from remote when missing locally.

```bash
aimake cache status
aimake cache pull
aimake cache push
```

## Step 8 — Record results

The state database stores:

- Build id, timestamps, which nodes ran
- New fingerprints and output locations
- Parsed metrics for quality gates and `aimake compare`
- Snapshots used by `aimake diff`
- Registry versions when `registry.auto_register` is on
- Optional lineage export (OpenLineage / MLflow / W&B)

```bash
aimake history
aimake logs <build-id>
aimake compare
aimake repro --format markdown
```

## On-disk layout

```text
.aimake/
├── state.db          # SQLite: builds, fingerprints, experiments, registry
├── cache/
│   └── <hash>/       # Content-addressable artifact outputs
└── logs/
    └── build-001.log
```

Project sources and declared `outputs/` live outside `.aimake/` (for example `build/evaluation/`). The cache is the durable, content-keyed copy; workspace outputs are the working tree.

## Why content hashing beats mtime

Make-style tools often rebuild when mtime is newer than the target. That fails for AI pipelines because:

- Checkouts and CI restores change mtimes without changing content
- Large binary blobs get rewritten identically by tools
- Prompt edits that matter are byte changes — exactly what SHA-256 captures
- Remote model drift is expressed as revision pins, not file clocks

aimake therefore treats **content + declared config** as the unit of change. See [Fingerprints & caching](/docs/caching).

## Debugging “why did this rebuild?”

```bash
aimake explain evaluation
aimake explain evaluation --tree
aimake explain evaluation --format json
aimake diff prompt --baseline stored
aimake diff dataset --baseline lock
```

`explain` walks fingerprint inputs and highlights the first mismatch. `diff` shows prompt / dataset / model deltas against stored, lock, or current baselines.

## Architecture map

High-level package layout inside the library:

```text
aimake/
├── cli.py              # Typer CLI
├── project.py          # Python API
├── config/             # YAML schema, loader, validation
├── graph/              # DAG, topological sort, planner
├── hashing/            # SHA-256 fingerprints, file-hash cache
├── cache/              # Local + S3 remote cache
├── scheduling/         # GPU pool, distributed workers
├── execution/          # Subprocess runner, parallel scheduler
├── state/              # SQLite state database
└── ...
```

More: [Architecture](/docs/architecture).

## Related guides

- [Core concepts](/docs/concepts) — vocabulary
- [Writing aimake.yaml](/docs/configuration) — declare the DAG
- [Fingerprints & caching](/docs/caching) — hit rates and remotes
- [CLI reference](/docs/cli) — every command
