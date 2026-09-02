---
title: Team & production
description: Shared team cache, monorepo --project, scheduled builds, Slack/Discord/email notifications, and secrets from Vault, Doppler, 1Password, or .env.
---

Production aimake setups share a **team cache**, run **monorepo** packages with `--project`, **schedule** nightly builds, **notify** on failure, and load **secrets** without baking keys into yaml.

Related: [Remote & team cache](/docs/remote-cache), [Artifact registry](/docs/registry), [CLI reference](/docs/cli), [Dashboard](/docs/dashboard).

## Shared team cache

```bash
aimake cache remote-init --bucket my-org-cache --team acme --region us-east-1
aimake build
git add aimake.yaml aimake.lock && git commit -m "Pin team cache"

# CI / teammate
aimake cache pull-lock
aimake build
```

Set `cache.remote.team_id` so every machine shares `{prefix}/{team_id}/`. Commit **`aimake.lock` v2** so fingerprints and remote identity stay aligned. Full detail: [Remote & team cache](/docs/remote-cache).

## Monorepo `--project` / `-P`

Each package can own its own `aimake.yaml`:

```text
repo/
├── apps/
│   └── rag/
│       ├── aimake.yaml
│       └── aimake.lock
└── services/
    └── eval/
        └── aimake.yaml
```

```bash
aimake build --project apps/rag
aimake plan -P apps/rag
aimake cache pull-lock -P apps/rag
aimake registry promote evaluation v2 --stage production -P apps/rag
aimake schedule --job nightly -P apps/rag
aimake secrets -P services/eval
aimake tui -P apps/rag
```

| Flag | Description |
|------|-------------|
| `--project`, `-P` | Path to a directory containing `aimake.yaml` |
| `--config`, `-c` | Explicit path to a yaml file |

Prefer `-P` in scripts so relative paths inside the subproject resolve correctly.

## Scheduled builds

### Ad-hoc cron

```bash
aimake schedule "0 6 * * *"              # every day 06:00 UTC
aimake schedule "0 6 * * *" --once       # next fire then exit
aimake schedule "0 6 * * *" --dry-run    # print next time only
aimake schedule "*/30 * * * *" --target evaluation --force
```

| Option / arg | Description |
|--------------|-------------|
| `[cron]` | Standard 5-field cron (UTC) |
| `--job`, `-j` | Named job from yaml |
| `--once` | Single fire then exit |
| `--dry-run`, `-n` | Show next run time |
| `--target`, `-t` | Restrict build targets |
| `--force`, `-f` | Force rebuild when the job runs |
| `--project`, `-P` | Monorepo subproject |

### Named jobs in yaml

```yaml
schedule:
  jobs:
    nightly:
      cron: "0 6 * * *"
      targets: [evaluation, report]
      force: false
      enabled: true
    hourly-eval:
      cron: "0 * * * *"
      targets: [evaluation]
      enabled: true
```

```bash
aimake schedule --job nightly --once
aimake schedule --job hourly-eval --dry-run
```

Disabled jobs (`enabled: false`) refuse to start. Press Ctrl+C to stop a long-running scheduler loop.

## Notifications

```yaml
notifications:
  slack:
    enabled: true
    webhook_env: SLACK_WEBHOOK_URL
    on_fail: true
    on_quality_gate: true
    on_cost_spike: true
    on_success: false
  discord:
    enabled: true
    webhook_env: DISCORD_WEBHOOK_URL
    on_fail: true
    on_quality_gate: true
    on_cost_spike: true
    on_success: false
  email:
    enabled: true
    smtp_host: smtp.example.com
    smtp_port: 587
    smtp_user_env: SMTP_USER
    smtp_password_env: SMTP_PASSWORD
    from_addr: aimake@example.com
    to_addrs: [ml-platform@example.com]
    use_tls: true
    on_fail: true
    on_quality_gate: true
    on_cost_spike: true
    on_success: false

policy:
  cost_spike_usd: 5.0     # triggers cost_spike notifications
```

| Channel | Required env / fields |
|---------|------------------------|
| Slack | `SLACK_WEBHOOK_URL` (or custom `webhook_env`) |
| Discord | `DISCORD_WEBHOOK_URL` |
| Email | SMTP host + optional user/password env vars, `to_addrs` |

### Test notifications

```bash
aimake notify-test
aimake notify-test --event fail
aimake notify-test --event success
aimake notify-test --event quality_gate
aimake notify-test --event cost_spike
```

| `--event` | Description |
|-----------|-------------|
| `fail` | Build failure (default) |
| `success` | Successful build |
| `quality_gate` | Quality gate failure |
| `cost_spike` | Plan/build cost over `policy.cost_spike_usd` |

If nothing is sent, enable the channel and set the webhook / SMTP env vars — `aimake notify-test` will say so.

## Secrets

aimake can load secrets into the process environment **before** builds. `aimake secrets` lists **key names only**, never values.

```yaml
secrets:
  dotenv: true
  dotenv_path: .env          # optional; default project-root .env
  providers:
    - type: vault
      path: secret/data/aimake
      addr_env: VAULT_ADDR
      token_env: VAULT_TOKEN
    - type: doppler
      project: aimake
      config: prod
    - type: onepassword
      vault: Engineering
      item: aimake-prod
    - type: env             # pass-through / validation helper
```

### `.env`

```bash
# .env (gitignored)
OPENAI_API_KEY=sk-...
HF_TOKEN=hf_...
```

With `secrets.dotenv: true` (default), keys are loaded if not already set in the environment.

### Vault

Requires the `vault` CLI on `PATH`, plus `VAULT_ADDR` / `VAULT_TOKEN` (or custom env names).

```yaml
- type: vault
  path: secret/data/aimake
```

### Doppler

Requires the `doppler` CLI.

```yaml
- type: doppler
  project: aimake
  config: prod
```

### 1Password

Requires the `op` CLI, signed in.

```yaml
- type: onepassword
  vault: Engineering
  item: aimake-prod
```

### Inspect loaded sources

```bash
aimake secrets
aimake secrets -P apps/rag
```

Output shows `.env` key counts and per-provider success/failure — **never secret values**.

## Registry + policy in production

```bash
aimake registry tag evaluation v9 champion
AIMAKE_APPROVE_PROD=1 aimake registry promote evaluation v9 --stage production
```

Configure `policy.promote` and `registry.remote` as documented in [Artifact registry](/docs/registry).

## Suggested production checklist

1. `aimake cache remote-init --team …` and commit yaml + lock after a green build  
2. CI: `pull-lock` → `build` → `eval --check` → optional `registry promote`  
3. `schedule.jobs` or `aimake schedule` for nightly evals  
4. Slack/Discord webhooks + `notify-test`  
5. Secrets via Doppler/Vault/1Password — keep `.env` local only  
6. `attestation` + `aimake repro` for audit trails ([Trust](/docs/trust))  
7. Dashboard Settings page for a live view of notifications / secrets / policy  

## Related

- [Remote & team cache](/docs/remote-cache)
- [Artifact registry](/docs/registry)
- [Trust & reproducibility](/docs/trust)
- [CI/CD](/docs/ci-cd)
- [Dashboard](/docs/dashboard)
- [CLI reference](/docs/cli)
