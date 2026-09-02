---
title: Security
description: Secrets handling, attestation, policy gates, log redaction, and what aimake does and does not store.
---

aimake runs **your** commands locally (or on workers you configure). Treat `aimake.yaml` like a Makefile: review it before building, especially from untrusted sources. There is no remote code execution and no automatic download of pipeline configs from the network.

Related: [Architecture](/docs/architecture), [Team & production](/docs/team), [Trust & reproducibility](/docs/trust), [Plugins](/docs/plugins).

---

## Executable configuration

| Risk | Mitigation |
|------|------------|
| `command:` runs arbitrary shell/Python | Review yaml; use trusted repos; pin CI to known commits |
| Plugins wrap commands (Docker) | Audit `metadata.docker` images and volumes |
| SSH workers | Limit `workers` to hosts you control; use least privilege |

aimake does **not** auto-fetch or execute remote `aimake.yaml` files.

---

## Secrets handling

### Loading

```yaml
secrets:
  dotenv: true                 # default: load project .env
  dotenv_path: .env            # optional override
  providers:
    - type: vault
      path: secret/data/aimake
      addr_env: VAULT_ADDR
      token_env: VAULT_TOKEN
    - type: doppler
      project: my-app
      config: prd
    - type: onepassword
      vault: Engineering
      item: aimake-prod
```

Secrets are injected into the **process environment** before builds. Supported providers use their CLIs (`vault`, `doppler`, `op`).

```bash
aimake secrets    # lists loaded key names only — never values
```

### Redaction

Environment variables whose names contain `KEY`, `SECRET`, `TOKEN`, or `PASSWORD` are redacted in:

- Fingerprint material when env **values** would otherwise be hashed
- Subprocess / log output helpers

Redacted placeholder: `***REDACTED***`.

### What to put where

| Store | Examples |
|-------|----------|
| `.env` (gitignored) | Local `OPENAI_API_KEY`, `HF_TOKEN` |
| Vault / Doppler / 1Password | Shared team credentials |
| CI secret store | GitHub Actions secrets → `env:` on the job |
| `aimake.yaml` | **Never** paste live API keys |

Plugin token knobs (`token_env`, `api_key_env`) should name env vars — not embed secrets.

---

## Policy gates

Promote to staging/production can require metric thresholds, cost caps, tags, and an approval env var:

```yaml
policy:
  promote:
    stages: [production]
    metrics:
      accuracy:
        min: 0.85
        required: true
    max_cost_usd: 2.0
    require_tag: reviewed
    require_approval_env: AIMAKE_APPROVE_PROD
  cost_spike_usd: 10.0
```

Enforced in:

- CLI: `aimake registry promote …` (use `--force` only when you intentionally bypass)
- Dashboard / API: `POST /api/registry/promote` and `GET /api/policy/check`
- Python: `Project.registry_promote` / `policy_check_promote`

Notifications can alert on fail, quality gate, and cost spike — see [Team & production](/docs/team).

---

## Attestation

```yaml
attestation:
  enabled: true
  write_sidecars: true      # .aimake/attestations/
  embed_in_metadata: true
  include_environment: true
```

When enabled, successful builds write **SLSA-lite / in-toto-style provenance** (unsigned JSON) describing artifact name, fingerprint, outputs (with digests when files exist), command, dependencies, git tip, and optional environment summary.

```bash
aimake repro --format markdown   # includes attestation presence
```

Attestations help **audit and repro reports**; they are not a substitute for signed supply-chain verification unless you add external signing.

---

## What aimake stores

| Stored | Where | Notes |
|--------|-------|-------|
| Fingerprints, build history, metrics | `.aimake/state.db` | Local SQLite |
| Cached outputs | `.aimake/cache/` | Content-addressable blobs |
| Lock / remote pin | `aimake.lock` | Safe to commit; no secret values |
| Attestations / lineage | `.aimake/attestations/`, `.aimake/lineage/` | Provenance & export JSON |
| Settings summary via API | `/api/settings` | Provider **types** and dotenv flag — not secret values |

## What aimake does **not** store

- Secret **values** in `state.db`, lockfiles, or `aimake secrets` output
- Cloud accounts beyond what **you** configure (S3, Hub, W&B)
- Automatic telemetry of pipeline contents (plugins may talk to third parties only when enabled — HF, W&B, etc.)
- A hosted multi-tenant secret vault (use Vault/Doppler/1Password)

The TypeScript client and dashboard settings endpoints expose configuration **shape**, not credential payloads.

---

## Remote cache and registry

- S3 credentials come from the environment / standard AWS resolution — not from aimake’s DB
- `cache.remote.team_id` namespaces shared prefixes; commit `aimake.lock` after green builds
- Registry remotes (S3 / HF / W&B) push **artifacts you promote**, gated by policy

See [Remote & team cache](/docs/remote-cache) and [Artifact registry](/docs/registry).

---

## Practical checklist

1. Gitignore `.env` and `.aimake/cache/`
2. Review PRs that change `command:` or Docker images
3. Enable `policy.promote` before production registry stages
4. Turn on `attestation.enabled` for audit trails
5. Use `aimake secrets` / doctor to confirm keys loaded without printing values
6. Prefer `environment_mode: names` (default) so secret values are not part of fingerprints
