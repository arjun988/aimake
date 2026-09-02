---
title: Artifact registry
description: Versioned artifact registry — list, show, promote, tag, push; policy.promote gates; registry.remote for S3, Hugging Face, and W&B.
---

The registry versions pipeline artifacts (models, evaluations, reports, …) with stages, tags, fingerprints, and optional **remote push** after promote. Use it to pin “what we ship” separately from ephemeral build outputs.

Related: [CLI reference](/docs/cli#artifact-registry), [Experiments](/docs/experiments), [Team & production](/docs/team), [Dashboard](/docs/dashboard).

## Enable the registry

```yaml
registry:
  enabled: true
  auto_register: true
  default_stage: dev          # dev | staging | production
```

| Field | Description |
|-------|-------------|
| `enabled` | Turn on registry recording |
| `auto_register` | Register successful builds automatically |
| `default_stage` | Initial stage for new versions (`dev`, `staging`, or `production`) |

Entries live in `.aimake/state.db` and appear in `aimake registry list` and the dashboard **Registry** page.

## CLI

### List

```bash
aimake registry list
aimake registry list --artifact evaluation
aimake registry list --stage production
aimake registry list --tag best
aimake registry list -a evaluation -s staging -n 20
```

| Option | Description |
|--------|-------------|
| `--artifact`, `-a` | Filter by artifact name |
| `--stage`, `-s` | Filter by stage |
| `--tag`, `-t` | Filter by tag |
| `--limit`, `-n` | Max rows (default `50`) |

### Show

```bash
aimake registry show evaluation v3
```

Prints stage, fingerprint, build id, tags, and metrics.

### Tag

```bash
aimake registry tag evaluation v3 best champion
aimake registry tag evaluation v3 best -P apps/rag
```

| Args | Description |
|------|-------------|
| `<artifact>` `<version>` | Target entry |
| `<tags...>` | One or more tags to add |

### Promote

```bash
aimake registry promote evaluation v3 --stage production
aimake registry promote evaluation v3 --stage staging
aimake registry promote evaluation v3 --stage production --force    # skip policy
aimake registry promote evaluation v3 --stage production --no-push  # skip remote
```

| Option | Description |
|--------|-------------|
| `--stage`, `-s` | Target stage (default `production`) |
| `--force` | Skip `policy.promote` gates |
| `--no-push` | Do not push to `registry.remote` even if configured |
| `--project`, `-P` | Monorepo subproject |

Promote is **policy-gated** when `policy.promote` is set (see below). With `registry.remote.auto_push_on_promote: true` (default), a successful promote also pushes to the remote backend unless `--no-push` is set.

### Push

```bash
aimake registry push evaluation v3
aimake registry push evaluation v3 -P apps/rag
```

Uploads an existing version to `registry.remote` without changing stage.

## Promote policy (`policy.promote`)

Gate production (or other stages) on metrics, cost, tags, and an approval env var:

```yaml
policy:
  promote:
    stages: [production]
    metrics:
      accuracy:
        minimum: 0.85
        required: true
      latency_ms:
        maximum: 800
    max_cost_usd: 2.50
    require_tag: champion
    require_approval_env: AIMAKE_APPROVE_PROD
  cost_spike_usd: 5.0          # also used for notifications
```

| Field | Description |
|-------|-------------|
| `stages` | Stages that enforce this policy (default includes `production`) |
| `metrics` | Same shape as quality gates (`minimum` / `maximum` / `required`) |
| `max_cost_usd` | Reject promote if recorded cost exceeds this |
| `require_tag` | Entry must already carry this tag |
| `require_approval_env` | Env var that must be set (e.g. `AIMAKE_APPROVE_PROD=1`) |

```bash
# Fails if gates fail
aimake registry promote evaluation v3 --stage production

# CI / emergency override
AIMAKE_APPROVE_PROD=1 aimake registry promote evaluation v3 --stage production
aimake registry promote evaluation v3 --stage production --force
```

The dashboard registry UI and `/api/policy/check` enforce the same rules.

## Remote registry (`registry.remote`)

Push promoted (or manually pushed) artifacts to S3, Hugging Face, or Weights & Biases.

### S3

```yaml
registry:
  enabled: true
  remote:
    type: s3
    auto_push_on_promote: true
    s3:
      bucket: my-org-artifacts
      prefix: aimake/registry/
      region: us-east-1
      # endpoint_url: https://minio.example.com
```

Requires `pip install aimake[s3]` and AWS credentials (same as [remote cache](/docs/remote-cache)).

### Hugging Face

```yaml
registry:
  enabled: true
  remote:
    type: huggingface
    auto_push_on_promote: true
    huggingface:
      repo_id: my-org/eval-artifacts
      token_env: HF_TOKEN
      private: true
```

```bash
pip install aimake[huggingface]
export HF_TOKEN=...
aimake registry push evaluation v3
```

### Weights & Biases

```yaml
registry:
  enabled: true
  remote:
    type: wandb
    auto_push_on_promote: true
    wandb:
      entity: my-team
      project: rag-prod
      api_key_env: WANDB_API_KEY
      type: model
```

```bash
pip install aimake[wandb]
export WANDB_API_KEY=...
aimake registry promote evaluation v3 --stage production
```

### Remote fields

| Field | Description |
|-------|-------------|
| `type` | `s3`, `huggingface`, or `wandb` |
| `auto_push_on_promote` | Push automatically after promote (default `true`) |
| `s3` / `huggingface` / `wandb` | Backend-specific block (required for the chosen type) |

## Typical workflow

```bash
aimake build
aimake compare previous latest
aimake registry list --artifact evaluation

aimake registry tag evaluation v4 champion
AIMAKE_APPROVE_PROD=1 aimake registry promote evaluation v4 --stage production
# → policy checks → stage=production → remote push

aimake registry show evaluation v4
```

## Stages & tags

| Concept | Use |
|---------|-----|
| **Stage** | Lifecycle: `dev` → `staging` → `production` |
| **Tag** | Soft labels: `best`, `champion`, `baseline`, release names |
| **Fingerprint** | Content hash tying the version to cache / lock |

Tags do not replace stages — use tags for selection (`require_tag`, dashboard filters) and stages for promotion gates.

## Related

- [CLI reference](/docs/cli)
- [Remote & team cache](/docs/remote-cache)
- [Trust & reproducibility](/docs/trust)
- [Team & production](/docs/team)
- [Dashboard](/docs/dashboard)
