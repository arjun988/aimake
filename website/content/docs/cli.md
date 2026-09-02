---
title: CLI reference
description: Complete aimake command reference — build, plan, cache, registry, plugins, schedule, trust, and monorepo --project.
---

The `aimake` CLI is a Typer app. Every command runs against an `aimake.yaml` in the current directory (or a path you pass with `--config` / `--project`).

```bash
aimake --version    # or -V
aimake --help
aimake <command> --help
```

Related guides: [Remote & team cache](/docs/remote-cache), [GPU & workers](/docs/workers), [Experiments](/docs/experiments), [Artifact registry](/docs/registry), [Trust](/docs/trust), [Team & production](/docs/team), [Dashboard](/docs/dashboard).

## Global options

| Option | Description |
|--------|-------------|
| `--version`, `-V` | Print version and exit |
| `--help` | Show help |

Most commands also accept:

| Option | Description |
|--------|-------------|
| `--config`, `-c` | Path to `aimake.yaml` |
| `--project`, `-P` | Monorepo subproject path (e.g. `apps/rag`) containing `aimake.yaml` |

See [Monorepo `--project`](#monorepo-project--p) below and [Team & production](/docs/team).

---

## Project lifecycle

### `aimake init`

Initialize a new aimake project (config, `.aimake/`, and usually `build/`).

```bash
aimake init
aimake init --path ./my-app --name my-rag-app
aimake init --from makefile
aimake init --from dvc
aimake init --from prefect
aimake init --from airflow-dag
```

| Option | Description |
|--------|-------------|
| `--path`, `-p` | Project directory (default: cwd) |
| `--name`, `-n` | Project name written into `aimake.yaml` |
| `--from` | Generate from an existing layout: `makefile`, `dvc`, `prefect`, `airflow-dag` |

With `--from`, review generated commands before the first build.

### `aimake build`

Build the dependency graph incrementally — skip unchanged nodes, restore from cache, or run stale steps.

```bash
aimake build
aimake build evaluation report
aimake build --force
aimake build evaluation --force
aimake build --dry-run
aimake build --jobs 4
aimake build -v --debug
aimake build --project apps/rag
```

| Option / arg | Description |
|--------------|-------------|
| `[targets...]` | Optional artifact names; default is the full graph |
| `--force`, `-f` | Force rebuild (all targets, or only named targets) |
| `--dry-run`, `-n` | Show plan without executing |
| `--jobs`, `-j` | Parallel jobs (`0` = auto) |
| `--verbose`, `-v` | Verbose output |
| `--debug` | Debug fingerprinting |
| `--config`, `-c` | Config path |
| `--project`, `-P` | Monorepo subproject |

On failure, aimake prints failed targets and relevant lines from `.aimake/logs/build-NNN.log`.

### `aimake plan`

Show what would run, skip, or restore — including estimated cost and tokens when `cost_estimate` is set.

```bash
aimake plan
aimake plan evaluation
aimake plan --format json
aimake plan -P apps/rag
```

| Option / arg | Description |
|--------------|-------------|
| `[targets...]` | Subgraph to plan |
| `--format`, `-f` | `text` (default) or `json` |
| `--debug` | Debug mode |
| `--config`, `-c` / `--project`, `-P` | Config selection |

JSON includes `to_run`, `to_skip`, `to_restore`, cost totals, and per-entry reasons — useful in CI.

### `aimake status`

Show per-artifact status (`UP TO DATE`, `CHANGED`, `STALE`, …).

```bash
aimake status
aimake status embeddings index
```

### `aimake clean`

Remove generated build outputs.

```bash
aimake clean
aimake clean embeddings index
aimake clean --all          # also clear local cache
```

| Option | Description |
|--------|-------------|
| `--all` | Clear `.aimake/cache/` in addition to build outputs |
| `[targets...]` | Limit cleaning to named artifacts |

### `aimake doctor`

Project health checks (config, dirs, cache, attestation flags, etc.). Exits non-zero on `ERROR` issues.

```bash
aimake doctor
```

---

## Inspection & debugging

### `aimake graph`

Display the dependency DAG.

```bash
aimake graph
aimake graph --format ascii    # default
aimake graph --format json
aimake graph --format dot
aimake graph --serve --port 8765   # same API as aimake serve
```

| Option | Description |
|--------|-------------|
| `--format`, `-f` | `ascii`, `json`, or `dot` |
| `--serve` | Start the dashboard API instead of printing |
| `--host` | Bind host with `--serve` (default `127.0.0.1`) |
| `--port`, `-p` | API port with `--serve` (default `8765`) |

See [Dashboard](/docs/dashboard).

### `aimake inspect`

Detailed info for one artifact (status, fingerprint, deps, files, size).

```bash
aimake inspect evaluation
```

### `aimake explain`

Explain why a target is stale (root cause chain, fingerprints, optional cost tree).

```bash
aimake explain report
aimake explain report --tree
aimake explain report --format json
```

| Option | Description |
|--------|-------------|
| `--tree` | Dependency tree with costs / validation / external notes |
| `--format`, `-f` | `text` or `json` |
| `--debug` | Debug fingerprinting |

### `aimake history`

Previous builds from `.aimake/state.db`.

```bash
aimake history
aimake history --limit 50
```

| Option | Description |
|--------|-------------|
| `--limit`, `-n` | Max rows (default `20`) |

### `aimake logs`

Print the log file for a build id.

```bash
aimake logs 3
# → .aimake/logs/build-003.log
```

### `aimake diff`

Show what changed for an artifact (prompt unified diff, dataset/model stats, fingerprint delta).

```bash
aimake diff prompt
aimake diff dataset --baseline lock
aimake diff model --baseline stored
aimake diff embeddings --baseline current
```

| Option | Description |
|--------|-------------|
| `--baseline`, `-b` | `stored` (default), `lock`, or `current` |

---

## Evaluation

### `aimake eval`

Quality gate checks against metrics from the latest build.

```bash
aimake eval --check
```

| Option | Description |
|--------|-------------|
| `--check` | Evaluate `quality_gates` in `aimake.yaml`; exit `1` on failure |

Without `--check`, aimake prints a hint to use `--check`. Ideal for CI after `aimake build`.

---

## Remote cache

Full guide: [Remote & team cache](/docs/remote-cache).

```bash
aimake cache status
aimake cache remote-init --bucket my-cache --team acme --region us-east-1
aimake cache push
aimake cache pull
aimake cache pull-lock
aimake cache sync
```

| Command | Options / args | Description |
|---------|----------------|-------------|
| `cache status` | `-c` | Local + remote + team summary |
| `cache push [fingerprint]` | `-c` | Push local entries to S3 |
| `cache pull [fingerprint]` | `-c` | Pull from S3 |
| `cache sync` | `-c`, `-P` | Pull missing, then push new |
| `cache remote-init` | `--bucket`/`-b`, `--prefix`, `--region`/`-r`, `--endpoint`, `--team`/`-t`, `-c`, `-P` | Write `cache.remote` into yaml |
| `cache pull-lock` | `-c`, `-P` | Pull fingerprints pinned in `aimake.lock` |

Requires `pip install aimake[s3]` and AWS (or S3-compatible) credentials.

---

## GPU & workers

```bash
aimake workers
```

Shows local GPU pool and SSH worker availability. See [GPU & workers](/docs/workers).

---

## Experiments

Full guide: [Experiments](/docs/experiments).

```bash
aimake compare
aimake compare 3 5
aimake compare previous latest
aimake optimize
aimake optimize --dry-run
aimake optimize -n 20 --name tuning-v2
aimake experiments list
aimake experiments show 1
```

| Command | Options / args | Description |
|---------|----------------|-------------|
| `compare` | `[baseline]` `[candidate]` | Metric deltas (`previous`/`latest`/build id) |
| `optimize` | `--trials`/`-n`, `--dry-run`, `--name`, `-c` | Hyperparameter search from `optimization:` |
| `experiments list` | `--limit`/`-n` | List optimization runs |
| `experiments show` | `<id>` | Trials for one experiment |

---

## Artifact registry

Full guide: [Artifact registry](/docs/registry).

```bash
aimake registry list
aimake registry list --artifact evaluation --stage production
aimake registry list --tag best
aimake registry show evaluation v1
aimake registry promote evaluation v1 --stage production
aimake registry promote evaluation v1 --stage production --force
aimake registry promote evaluation v1 --no-push
aimake registry push evaluation v1
aimake registry tag evaluation v1 best champion
```

| Command | Options | Description |
|---------|---------|-------------|
| `list` | `--artifact`/`-a`, `--stage`/`-s`, `--tag`/`-t`, `--limit`/`-n` | List versions |
| `show` | `<artifact>` `<version>` | Detail one entry |
| `promote` | `--stage`/`-s`, `--force`, `--no-push`, `-P` | Promote (policy-gated) |
| `push` | `<artifact>` `<version>`, `-P` | Push to `registry.remote` |
| `tag` | `<artifact>` `<version>` `<tags...>` | Add tags |

Requires `registry.enabled: true`.

---

## Watch, serve, TUI

### `aimake watch`

Poll inputs and re-plan when files change.

```bash
aimake watch
aimake watch --interval 1.5
aimake watch --build          # auto-build on change
```

| Option | Description |
|--------|-------------|
| `--interval`, `-i` | Poll interval in seconds (default `2.0`) |
| `--build`, `-b` | Rebuild when a change is detected |

### `aimake serve`

Start the dashboard JSON API (pair with the Next.js UI).

```bash
aimake serve
aimake serve --port 8765 --host 127.0.0.1
aimake serve --open           # opens http://localhost:3000 hint
```

| Option | Description |
|--------|-------------|
| `--host` | Bind host (default `127.0.0.1`) |
| `--port`, `-p` | API port (default `8765`) |
| `--open` | Open the dashboard URL hint in a browser |
| `--config`, `-c` | Config path |

See [Dashboard](/docs/dashboard).

### `aimake tui`

Interactive full-screen Rich TUI — plan, build, and metrics.

```bash
aimake tui
aimake tui --project apps/rag
```

---

## Team: schedule, notify, secrets

Full guide: [Team & production](/docs/team).

### `aimake schedule`

Run builds on a cron expression or a named `schedule.jobs` entry.

```bash
aimake schedule "0 6 * * *"
aimake schedule "0 6 * * *" --once
aimake schedule "0 6 * * *" --dry-run
aimake schedule --job nightly --once
aimake schedule "*/30 * * * *" --target evaluation --force
```

| Option / arg | Description |
|--------------|-------------|
| `[cron]` | Cron expression (UTC), e.g. `0 6 * * *` |
| `--job`, `-j` | Named job from `schedule.jobs` |
| `--once` | Run on next match then exit |
| `--dry-run`, `-n` | Print next fire time only |
| `--target`, `-t` | Build targets (repeatable) |
| `--force`, `-f` | Force rebuild when the job fires |
| `--project`, `-P` | Monorepo subproject |

### `aimake notify-test`

Send a test notification via configured Slack / Discord / email channels.

```bash
aimake notify-test
aimake notify-test --event success
aimake notify-test --event quality_gate
aimake notify-test --event cost_spike
```

| Option | Description |
|--------|-------------|
| `--event`, `-e` | `fail` (default), `success`, `quality_gate`, or `cost_spike` |

### `aimake secrets`

Show which secrets sources loaded (**keys only**, never values).

```bash
aimake secrets
aimake secrets -P apps/rag
```

---

## Trust & reproducibility

Full guide: [Trust & reproducibility](/docs/trust).

### `aimake probe`

Probe external model/API deps marked `probe: true` for revision drift. Exit code `2` if drift is detected.

```bash
aimake probe
```

### `aimake repro`

Generate a reproducibility report (env, fingerprints, git, drift, attestations).

```bash
aimake repro
aimake repro --format markdown
aimake repro --format json -o repro.json
aimake repro --format pdf
```

| Option | Description |
|--------|-------------|
| `--format`, `-f` | `markdown` (default), `json`, or `pdf` |
| `--output`, `-o` | Output path |
| `--project`, `-P` | Monorepo subproject |

### `aimake lineage`

Export pipeline lineage as OpenLineage / MLflow / W&B graph JSON.

```bash
aimake lineage
aimake lineage --format openlineage --format mlflow
aimake lineage -f wandb -o .aimake/lineage
```

| Option | Description |
|--------|-------------|
| `--format`, `-f` | `openlineage`, `mlflow`, and/or `wandb` (repeatable) |
| `--output-dir`, `-o` | Directory for exported files |

---

## Plugins

```bash
aimake plugins
```

Lists enabled plugins and built-in integration status (HF, W&B, DVC, Docker, Ollama, MLflow, Optuna, S3).

Enable plugins under `plugins.*.enabled: true` in `aimake.yaml`. See [Plugins overview](/docs/plugins).

### Hugging Face (`aimake hf`)

```bash
pip install aimake[huggingface]
aimake hf pull embedder
aimake hf push embedder
aimake hf status
aimake hf status embedder
```

| Command | Description |
|---------|-------------|
| `hf pull <artifact>` | Download from the Hub |
| `hf push <artifact>` | Upload to the Hub |
| `hf status [artifact]` | Show Hub linkage |

### Weights & Biases (`aimake wandb`)

```bash
pip install aimake[wandb]
aimake wandb sync evaluation
aimake wandb status
```

| Command | Description |
|---------|-------------|
| `wandb sync <artifact>` | Log metrics/artifacts |
| `wandb status [artifact]` | Show W&B linkage |

### DVC (`aimake dvc`)

```bash
pip install aimake[dvc]
aimake dvc pull dataset
aimake dvc push dataset
aimake dvc status
```

| Command | Description |
|---------|-------------|
| `dvc pull <artifact>` | Pull DVC-tracked data |
| `dvc push <artifact>` | Push DVC-tracked data |
| `dvc status [artifact]` | Show DVC linkage |

### Docker (`aimake docker`)

```bash
pip install aimake[docker]
aimake docker build train
aimake docker status
```

| Command | Description |
|---------|-------------|
| `docker build <artifact>` | Build the artifact’s image |
| `docker status [artifact]` | Show Docker config / whether image exists |

### Ollama (`aimake ollama`)

```bash
pip install aimake[ollama]
aimake ollama pull local_llm
aimake ollama status
```

| Command | Description |
|---------|-------------|
| `ollama pull <artifact>` | Pull the configured Ollama model |
| `ollama status [artifact]` | Show model / host / local presence |

---

## Monorepo `--project` / `-P`

In a monorepo, each package can own an `aimake.yaml`. Point the CLI at a subproject:

```bash
aimake build --project apps/rag
aimake plan -P apps/rag
aimake cache pull-lock -P services/eval
aimake registry promote evaluation v3 --stage production -P apps/rag
aimake tui -P apps/rag
```

Commands that accept `-P` include (among others): `build`, `plan`, `status`, `tui`, `cache sync|remote-init|pull-lock`, `registry promote|push|tag`, `schedule`, `notify-test`, `secrets`, `repro`, `lineage`, `probe`.

Equivalent forms:

```bash
aimake build -c apps/rag/aimake.yaml
aimake build -P apps/rag
```

---

## Command tree

```text
aimake
├── init | build | plan | status | clean | doctor
├── graph | inspect | explain | history | logs | diff | eval
├── watch | serve | tui
├── workers | compare | optimize
├── schedule | notify-test | secrets | plugins
├── probe | repro | lineage
├── cache → status | push | pull | sync | remote-init | pull-lock
├── experiments → list | show
├── registry → list | show | promote | push | tag
├── hf → pull | push | status
├── wandb → sync | status
├── dvc → pull | push | status
├── docker → build | status
└── ollama → pull | status
```
