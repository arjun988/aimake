---
title: Changelog
description: Summary of aimake releases from 1.7.0 back through notable earlier versions — full history on GitHub.
---

Summarized from the repository [CHANGELOG.md](https://github.com/arjun988/aimake/blob/main/CHANGELOG.md). aimake follows [Semantic Versioning](https://semver.org/) and [Keep a Changelog](https://keepachangelog.com/).

**Full history & compare links:** [github.com/arjun988/aimake/blob/main/CHANGELOG.md](https://github.com/arjun988/aimake/blob/main/CHANGELOG.md) · [Releases](https://github.com/arjun988/aimake/releases)

Related: [Contributing](/docs/contributing), [Docker](/docs/docker), [Python SDK](/docs/sdk-python), [Trust & reproducibility](/docs/trust).

---

## 1.7.0 — Docker, TUI, SDK parity

**2026-09-02**

- **Docker image:** `Dockerfile` + GHCR publish → [`ghcr.io/arjun988/aimake`](/docs/docker)
- **Interactive TUI:** [`aimake tui`](/docs/tui) — Rich full-screen plan / build / metrics
- **SDK parity:** `aimake.sdk.Aimake` / `load()`, TypeScript [`@aimake/sdk`](/docs/sdk-typescript), docs
- Dashboard **Developer** page + `/api/developer`

---

## 1.6.0 — Trust & correctness

**2026-09-02**

- External drift **probes** (`external.probe`, `aimake probe`)
- Custom **validation.command** after structural checks
- **Attestation** (`attestation.enabled` → `.aimake/attestations/`)
- **Repro report** (`aimake repro`)
- **Partial restore** from cache (`RESTORE` when outputs missing)
- **Lineage export** (OpenLineage / MLflow / W&B)
- Dashboard `/repro`, `/lineage` and matching APIs

See [Security](/docs/security) and [Trust & reproducibility](/docs/trust).

---

## 1.5.0 — Team & production

**2026-09-02**

- Shared **team cache** (`team_id`, `cache remote-init`, `pull-lock`, lock v2)
- **Registry remote** (S3 / HF / W&B) + `registry push`
- **Promote policy** gates (CLI + dashboard)
- **Scheduled builds** (`aimake schedule`, `schedule.jobs`)
- **Notifications** (Slack / Discord / email)
- **Monorepo** `--project` / `-P`
- **Secrets** (`.env` + Vault / Doppler / 1Password)
- Settings / policy APIs on the dashboard

See [Team & production](/docs/team) and [Remote & team cache](/docs/remote-cache).

---

## 1.4.0 — Web dashboard

**2026-09-02**

- Next.js + Tailwind **dashboard** (overview, graph, builds, experiments, registry, cache)
- **`aimake serve`** JSON API
- **`aimake graph --serve`** for demos
- Registry promote / tag via dashboard POST endpoints

See [Dashboard](/docs/dashboard).

---

## 1.3.0 — Adoption hooks

**2026-09-02**

- `aimake init --from` generators: makefile, dvc, prefect, airflow-dag
- Official **GitHub Action** (cache, plan JSON, PR comments)
- **`aimake watch`**
- `aimake explain --tree` / `--format json`
- `aimake plan --format json`
- Comparison & adapter docs

See [Migration](/docs/migration), [CI/CD](/docs/ci-cd), [Comparison](/docs/comparison), [Adapters](/docs/adapters).

---

## 1.2.0 — Correctness & cost in plan

**2026-09-02**

- **External** dependencies on artifacts; `volatile` opt-out
- Environment fingerprint modes (`names` \| `values`)
- **Atomic outputs** + `resolve_output()`
- **Output validation** (size, keys, metric mins); revalidation on cache hit
- **Plan cost estimates** (`cost_estimate`, `$` / tokens in `aimake plan`)
- Quality gates: `required: true` for missing metrics

---

## 1.1.0 — Plugin pack

**2026-09-01**

- Plugins: **W&B**, **DVC**, **Docker**, **Ollama** (HF landed in 1.0)
- Extras: `wandb`, `dvc`, `plugins`; `PluginManager.wrap_command()`
- Pre-pull DVC / Ollama before planning

See [Plugins](/docs/plugins).

---

## 1.0.0 — Production core

**2026-09-01**

- Persistent file-hash cache; rich **diffs** + snapshots
- **S3 remote cache**; GPU scheduling; SSH **workers**
- Experiment **compare** / **optimize** (grid, random, Bayesian / Optuna, Hyperband)
- **Hugging Face** plugin; versioned **artifact registry**
- Hardening test suite

---

## 0.1.0 — Initial release

**2026-09-01**

- Incremental AI build system: CLI (`init`, `build`, `plan`, `status`, `graph`, …)
- Content-addressable local cache, SHA-256 fingerprints, parallel execution
- AI artifact types, quality gates, `aimake.lock`, example RAG pipeline
- Python `Project` API

---

## Unreleased

See the `[Unreleased]` section at the top of the GitHub changelog for work merged after the latest tagged release.
