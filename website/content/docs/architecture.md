---
title: Architecture
description: Dependency DAG, content fingerprints, .aimake/ layout, state.db, content-addressable cache, and the incremental execution model.
---

aimake is an incremental build system for AI pipelines: a **dependency DAG**, **content fingerprints**, a **SQLite state store**, and a **content-addressable cache** decide what to skip, restore, or run.

Related: [How aimake works](/docs/how-it-works), [Fingerprints & caching](/docs/caching), [Remote & team cache](/docs/remote-cache), [Security](/docs/security).

---

## Execution model (pipeline)

1. **Read** `aimake.yaml` and validate the schema (`aimake/config`)
2. **Construct** a dependency DAG from `depends_on` edges (`aimake/graph`)
3. **Fingerprint** each artifact from inputs, upstream fingerprints, command, parameters, environment, and optional `external` pins (`aimake/hashing`)
4. **Compare** fingerprints against `.aimake/state.db` and `aimake.lock`
5. **Plan** — for each node: `SKIP`, `RESTORE` (cache hit, missing outputs), or `RUN` (stale / missing / forced)
6. **Execute** commands in topological order; parallelize independent nodes (`aimake/execution`, optional GPU / SSH workers)
7. **Validate** outputs (structural checks + optional `validation.command`); promote atomically
8. **Cache** successful outputs under `.aimake/cache/<hash>/`
9. **Record** build metadata, metrics, snapshots, optional registry / attestation / lineage / plugin hooks

Fingerprints use **SHA-256 content hashes**, not timestamps. Changing a file’s mtime without changing content does **not** invalidate the cache.

---

## Dependency DAG

```text
dataset ──► embeddings ──► evaluation
prompt  ───────────────────┘
```

- Nodes are **artifacts** (`type`: dataset, model, prompt, embedding, vector_index, evaluation, report, …)
- Edges are `depends_on` lists
- `aimake plan` / `build` can target a subgraph (`targets=`)
- Cycles are rejected at load/validation time
- Visualization: `aimake graph`, dashboard Graph page, `Project.graph_dict()` / TS `ai.graph()`

Planner statuses feed the UI and TUI: fresh, stale, missing, etc. See [Core concepts](/docs/concepts).

---

## Fingerprints

A fingerprint typically mixes:

| Ingredient | Role |
|------------|------|
| Input file contents | `source` / tracked inputs |
| Upstream artifact fingerprints | DAG invalidation |
| Command string | Script / CLI changes |
| Parameters / optimization trial env | `AIMAKE_PARAM_*` |
| Environment | Default `environment_mode: names` (not live values) |
| `external` pins | provider / model / revision |
| Volatile flags | `volatile: true` / `volatile_environment` exclude noise |

A persistent **file-hash cache** inside `state.db` avoids re-hashing unchanged files within and across runs. Debug with `aimake --debug` / `aimake explain --tree`.

Lockfile: successful builds can write **`aimake.lock`** (v2 can pin remote team cache identity). CI/laptops restore with `aimake cache pull-lock` — [Remote & team cache](/docs/remote-cache).

---

## `.aimake/` layout

Created by `aimake init` and grown by builds:

```text
.aimake/
├── state.db              # SQLite: fingerprints, builds, experiments, registry, file-hash cache
├── cache/
│   └── <content-hash>/   # Content-addressable artifact outputs
├── logs/
│   └── build-*.log       # Per-build logs (`aimake logs`)
├── attestations/         # SLSA-lite provenance JSON (when attestation.enabled)
└── lineage/              # Exported OpenLineage / MLflow / W&B (when configured)
```

Also project-root:

| Path | Purpose |
|------|---------|
| `aimake.yaml` | Pipeline definition |
| `aimake.lock` | Logical reproducibility / remote pin |
| `.env` | Optional secrets (loaded when `secrets.dotenv` is true) |

Treat `.aimake/cache/` as disposable (rebuild or `aimake cache pull`). Commit `aimake.lock` when sharing fingerprints across machines; usually **gitignore** large cache blobs.

---

## `state.db`

SQLite database (thread-safe for parallel builds) holding:

- Last known fingerprint per artifact
- Build history (git tip, metrics, success/failure)
- Experiment / optimization trial records
- Registry versions and tags
- File-hash cache entries for fingerprinter speed
- Snapshots used by `aimake diff` / rich diffs

Opened by `Project` / `Aimake.load()`; always `close()` (or use a context manager) in long-lived processes.

---

## Cache

**Local:** content-addressable directories under `.aimake/cache/`. On a fingerprint hit with missing outputs → **RESTORE** (partial restore) instead of a full rebuild.

**Remote (optional):** S3-compatible bucket via `cache.remote` (+ `team_id` for shared prefixes). Commands: `aimake cache push|pull|sync|status|remote-init|pull-lock`.

**Atomic outputs:** stage → validate → promote; failed builds discard partials so corrupt artifacts are not left as “success.”

---

## Package map

```text
aimake/
├── cli.py              # Typer CLI
├── project.py          # Python API
├── sdk/                # Aimake.load() wrapper
├── config/             # YAML schema, loader, validation
├── graph/              # DAG, topological sort, planner
├── hashing/            # SHA-256 fingerprints, file-hash cache
├── cache/              # Local + S3 remote cache
├── scheduling/         # GPU pool, distributed workers
├── diff/               # Dataset/model/prompt diffs + snapshots
├── experiments/        # Compare, optimize, Hyperband, Pareto, MLflow
├── registry/           # Versioned artifact registry
├── plugins/            # HF, W&B, DVC, Docker, Ollama
├── execution/          # Subprocess runner, parallel scheduler
├── artifacts/          # Type-specific handlers
├── metrics/            # Metrics parsing, quality gates
├── policy/             # Promote / cost gates
├── secrets/            # .env + Vault / Doppler / 1Password
├── attest/             # SLSA-lite provenance
├── git/                # Git metadata
├── state/              # SQLite state database
├── serve/              # HTTP API for dashboard / TS SDK
└── ui/                 # Rich console + TUI
```

---

## Parallelism and workers

- Default: local process pool respecting DAG readiness and `jobs`
- `resources.gpu` reserves GPUs from a pool
- `workers:` SSH remotes for distributed steps (`aimake workers`)

See [GPU & workers](/docs/workers).

---

## Design principles

1. **Content over clock** — fingerprints, not mtimes  
2. **Plan before pay** — cost/token estimates on stale nodes  
3. **Skip or restore** — never re-run what you can prove unchanged  
4. **Fail closed on outputs** — validation + atomic promote  
5. **Complement, don’t replace** — plugins/adapters meet DVC, W&B, LangChain, orchestrators ([Comparison](/docs/comparison))
