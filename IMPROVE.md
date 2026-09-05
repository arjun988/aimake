# aimake — Adoption & Improvement Roadmap

Ideas to drive faster adoption, retention, and production use. Prioritized by impact and effort.

---

## Adopt immediately (high impact, clear hook)

| # | Feature | Why it matters |
|---|---------|----------------|
| 1 | **`aimake init --from` generators** | ✅ Done — `makefile`, `dvc`, `prefect`, `airflow-dag` |
| 2 | **One-command pipeline templates** | `aimake init --template=rag\|finetune\|eval-only\|agent` with working example — clone and run in 2 minutes |
| 3 | **VS Code / Cursor extension** | ✅ Done — [`extension/`](extension/) sidebar plan (stale/reuse/restore), status-bar cost, build/explain |
| 4 | **Official GitHub Action** | ✅ Done — `.github/actions/aimake` with cache + PR comment |
| 5 | **Remote cache that “just works”** | `aimake cache remote init` — cloud bucket setup in ~30 seconds (not only manual S3 YAML) |
| 6 | **Cost dashboard in CLI** | `aimake cost` / `aimake plan --cost` as a first-class story — see the bill before you pay |
| 7 | **LangChain / LlamaIndex / HF adapters** | ✅ Done — [docs/ADAPTERS.md](docs/ADAPTERS.md) |
| 8 | **`aimake watch`** | ✅ Done — `aimake watch [--build]` |
| 9 | **Better “why stale?” UX** | ✅ Done — `aimake explain --tree`, `--format json` |
| 10 | **Comparison docs** | ✅ Done — [docs/COMPARISON.md](docs/COMPARISON.md) | 

---

## Strong adoption (team & production)

| # | Feature | Why it matters |
|---|---------|----------------|
| 11 | **Web UI (lightweight)** | ✅ Done — Next.js + Tailwind dashboard + `aimake serve` / `aimake graph --serve` |
| 12 | **Shared team cache** | ✅ Done — `team_id`, `cache remote-init`, `pull-lock`, lock v2 remote pin |
| 13 | **Artifact registry with remote** | ✅ Done — S3 / HF / W&B push + `registry push` |
| 14 | **Policy / approval gates** | ✅ Done — `policy.promote` gates on CLI + dashboard |
| 15 | **Scheduled builds** | ✅ Done — `aimake schedule` + `schedule.jobs` |
| 16 | **Notifications** | ✅ Done — Slack / Discord / email + `notify-test` |
| 17 | **Multi-project monorepo** | ✅ Done — `--project` / `-P` |
| 18 | **Secrets integration** | ✅ Done — `.env` + Vault / Doppler / 1Password |

---

## Trust & correctness (why people stay)

| # | Feature | Why it matters |
|---|---------|----------------|
| 19 | **Auto-detect external model drift** | ✅ Done — `external.probe` + `aimake probe` |
| 20 | **Custom validation scripts** | ✅ Done — `validation.command` |
| 21 | **Output signing / attestation** | ✅ Done — SLSA-lite sidecars via `attestation.enabled` |
| 22 | **Reproducibility report** | ✅ Done — `aimake repro` (+ dashboard) |
| 23 | **Partial restore from cache** | ✅ Done — missing outputs → RESTORE on cache hit |
| 24 | **Lineage export** | ✅ Done — OpenLineage / MLflow / W&B + dashboard |

---

## Developer experience & ecosystem

| # | Feature | Why it matters |
|---|---------|----------------|
| 25 | **Docker image** | ✅ Done — `Dockerfile` + GHCR publish (`ghcr.io/.../aimake`) |
| 26 | **Plugin marketplace / entry points** | Third-party plugins without editing core (`pip install aimake-wandb-plus`) |
| 27 | **`aimake doctor --fix`** | Auto-fix missing dirs, suggest yaml fixes, detect stale partial outputs |
| 28 | **Interactive TUI** | ✅ Done — `aimake tui` Rich full-screen plan/build/metrics |
| 29 | **Jupyter integration** | `%aimake build evaluation` in notebooks — huge for researchers |
| 30 | **TypeScript / Python SDK parity** | ✅ Done — `aimake.sdk` + `@aimake/sdk` + [docs/SDK.md](docs/SDK.md) |

---

## Growth & distribution

| # | Feature | Why it matters |
|---|---------|----------------|
| 31 | **Benchmark / savings page** | “Prompt change: 45 min → 90 sec, $12 → $0.40” with reproducible example |
| 32 | **Content & listings** | Dev.to / YouTube 5-min demo, Awesome-LLM-Ops list |
| 33 | **GPU host integrations** | Modal, Replicate, RunPod, Lambda — “run GPU step on X” as one yaml block |
| 34 | **Free hosted cache for OSS** | Sign in with GitHub → 10GB cache — lower barrier vs rolling your own S3 |
| 35 | **Compatibility badge** | README badge showing cache hit rate / last build status |
| 36 | **Documentation website** | ✅ Done — Next.js + Tailwind docs site in [`website/`](website/) (port 3001) |

---

## Top 5 — highest adoption per engineering week

| Priority | Feature | Rationale |
|----------|---------|-----------|
| **1** | **GitHub Action + PR cost/quality comment** | Every ML team uses GitHub CI |
| **2** | **`aimake init --template=rag`** | Instant “it works” moment |
| **3** | **Market `aimake plan` cost + tokens** | Already shipped in v1.2.0 — lead with this in docs and demos |
| **4** | **LangChain / LlamaIndex one-liner integration** | Meet existing code, don’t replace it |
| **5** | **`aimake watch` + Cursor extension** | ✅ Extension shipped in [`extension/`](extension/); watch already done |

---

## Strategic positioning

aimake’s wedge is **incremental + cost-aware + AI-shaped** — not “another orchestrator.”

| Tool | Strength |
|------|----------|
| **Airflow / Prefect** | Scheduling and orchestration at scale |
| **DVC** | Data versioning |
| **Make** | Generic file dependencies |
| **aimake** | Skip unchanged AI pipeline steps; show cost before run; prompt/model/config-aware |

Double down on:

1. **Cost before run**
2. **Skip what didn’t change**
3. **5-minute template to first win**

---

## Already shipped (reference)

- Incremental builds, content fingerprints, parallel execution
- S3 remote cache, GPU scheduling, distributed workers
- Experiment compare, hyperparameter optimization, artifact registry
- Plugins: Hugging Face, W&B, DVC, Docker, Ollama
- v1.2.0: external dependencies, atomic outputs, output validation, plan cost estimates

See [CHANGELOG.md](CHANGELOG.md) for full release history.

---

## Contributing

Pick an item, open an issue, or PR with the feature number from this doc (e.g. “Implements #8: aimake watch”).
