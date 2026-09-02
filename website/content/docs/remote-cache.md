---
title: Remote & team cache
description: S3 remote cache, team_id prefixes, remote-init, push/pull/sync, pull-lock, and aimake.lock v2 for shared CI and laptop builds.
---

aimake’s local cache stores content-addressable artifact outputs under `.aimake/cache/`. A **remote cache** mirrors those blobs to S3 (or an S3-compatible store) so CI and teammates skip work that someone else already paid for.

For org-wide sharing, set a **`team_id`**, commit **`aimake.lock`** (v2), and use **`aimake cache pull-lock`** on cold machines. See also [Team & production](/docs/team) and [CLI reference](/docs/cli).

## Prerequisites

```bash
pip install aimake[s3]
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
# optional for custom endpoints
export AWS_DEFAULT_REGION=us-east-1
```

Works with AWS S3, MinIO, Cloudflare R2, and other S3-compatible APIs via `endpoint_url`.

## Quick start (team cache)

```bash
# From a project with aimake.yaml
aimake cache remote-init --bucket my-org-cache --team acme --region us-east-1

aimake build                 # auto_pull / auto_push; writes aimake.lock
git add aimake.yaml aimake.lock
git commit -m "Share team cache pin"

# On CI or another laptop
aimake cache pull-lock
aimake build                 # restores lock-pinned fingerprints when blobs exist
```

## Configuration

Manual YAML (equivalent to `remote-init`):

```yaml
cache:
  write_lock: true          # default — write aimake.lock after successful builds
  remote:
    type: s3
    auto_pull: true         # restore missing local entries during build
    auto_push: true         # upload after successful builds
    team_id: acme           # shared org prefix
    s3:
      bucket: my-org-cache
      prefix: aimake/cache/
      region: us-east-1
      # endpoint_url: https://minio.example.com
```

### Fields

| Field | Description |
|-------|-------------|
| `cache.remote.type` | Currently `s3` |
| `cache.remote.auto_pull` | Pull missing cache entries during builds (default `true`) |
| `cache.remote.auto_push` | Push new entries after successful builds (default `true`) |
| `cache.remote.team_id` | Optional shared team id — keys live under `{prefix}/{team_id}/` |
| `cache.remote.s3.bucket` | Bucket name |
| `cache.remote.s3.prefix` | Key prefix (default `aimake/cache/`) |
| `cache.remote.s3.region` | AWS region |
| `cache.remote.s3.endpoint_url` | Optional S3-compatible endpoint |
| `cache.write_lock` | Write `aimake.lock` after green builds (default `true`) |

### Effective key prefix

Without a team:

```text
s3://my-org-cache/aimake/cache/<fingerprint>/...
```

With `team_id: acme`:

```text
s3://my-org-cache/aimake/cache/acme/<fingerprint>/...
```

`remote-init` prints the team prefix so you can verify it matches across repos.

## CLI commands

### `aimake cache remote-init`

Writes `cache.remote` into `aimake.yaml` (creates the block if needed).

```bash
aimake cache remote-init \
  --bucket my-org-cache \
  --team acme \
  --region us-east-1 \
  --prefix aimake/cache/

# MinIO / R2-style
aimake cache remote-init \
  --bucket aimake \
  --endpoint https://minio.example.com \
  --team platform
```

| Option | Description |
|--------|-------------|
| `--bucket`, `-b` | S3 bucket (**required**) |
| `--prefix` | Key prefix (default `aimake/cache/`) |
| `--region`, `-r` | Region |
| `--endpoint` | S3-compatible endpoint URL |
| `--team`, `-t` | Shared org `team_id` |
| `--config`, `-c` / `--project`, `-P` | Config selection |

After init, commit the yaml change and run a successful `aimake build` so `aimake.lock` pins fingerprints + remote identity.

### `aimake cache status`

Local entry counts, remote configuration, and team prefix summary.

```bash
aimake cache status
```

### `aimake cache push` / `pull`

```bash
aimake cache push                 # all local entries not yet remote
aimake cache push <fingerprint>   # one entry
aimake cache pull
aimake cache pull <fingerprint>
```

Fails with a clear error if `cache.remote` is not configured.

### `aimake cache sync`

Pull missing remote entries, then push new local ones.

```bash
aimake cache sync
aimake cache sync -P apps/rag
```

### `aimake cache pull-lock`

Reads fingerprints from **`aimake.lock`** and pulls those blobs from the shared remote. Use this on a fresh CI checkout or a new laptop **before** (or as part of) the first build.

```bash
aimake cache pull-lock
aimake cache pull-lock --project apps/rag
```

Typical CI snippet:

```yaml
- run: pip install aimake[s3]
- run: aimake cache pull-lock
- run: aimake build
```

## aimake.lock v2

Successful builds with `cache.write_lock: true` write `aimake.lock` at the project root.

### Shape

```yaml
version: 2
project:
  name: my-rag-app
artifacts:
  dataset:
    fingerprint: "sha256:..."
  embeddings:
    fingerprint: "sha256:..."
  evaluation:
    fingerprint: "sha256:..."
cache:
  remote:
    type: s3
    team_id: acme
    bucket: my-org-cache
    prefix: aimake/cache/acme/    # team-qualified prefix
    region: us-east-1
    endpoint_url: null
```

| Field | Purpose |
|-------|---------|
| `version` | Lock format — **v2** includes remote identity |
| `project.name` | Project name from config |
| `artifacts.*.fingerprint` | Content fingerprints to restore |
| `cache.remote` | Bucket / team / prefix pin so CI uses the same remote as the authoring machine |

### Why commit the lock?

1. **Reproducibility** — teammates and CI target the same fingerprints, not “whatever is newest in S3”.
2. **Team cache pin** — v2 embeds remote identity (`team_id`, bucket, effective prefix).
3. **`pull-lock`** — only pulls the pinned set, avoiding accidental reuse of unrelated blobs.

Diffs can compare against the lock with:

```bash
aimake diff prompt --baseline lock
```

## Build-time behavior

During `aimake build`:

1. Fingerprints are computed for each artifact.
2. If a fingerprint is **up to date** locally → **SKIP**.
3. If the fingerprint is in the **local cache** but outputs are missing → **RESTORE** (see [Trust](/docs/trust)).
4. If missing locally and `auto_pull` is on → try **remote** restore.
5. After a successful run, new blobs are stored locally; with `auto_push` they upload to S3.
6. With `write_lock`, `aimake.lock` is refreshed.

Use `aimake plan` / `aimake plan --format json` to see `to_run`, `to_skip`, and `to_restore` before spending GPU or API budget.

## Operational tips

- **One `team_id` per org or product line** — isolate unrelated pipelines with different team ids or prefixes.
- **Commit lock after green main builds** — treat it like a package lockfile.
- **Secrets stay out of the cache** — only artifact outputs and fingerprints are stored; load API keys via [secrets](/docs/team#secrets).
- **Monorepos** — each subproject has its own yaml + lock; use `-P` with cache commands.
- **Dashboard** — Cache page shows local / remote / team status when [aimake serve](/docs/dashboard) is running.

## Related

- [CLI reference — cache](/docs/cli#remote-cache)
- [Fingerprints & caching](/docs/caching)
- [Team & production](/docs/team)
- [Dashboard](/docs/dashboard)
