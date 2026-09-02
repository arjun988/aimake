---
title: Fingerprints & caching
description: How SHA-256 fingerprints decide rebuilds, how the local content-addressable cache works, and how to sync an S3 remote / team cache.
---

## Why caching matters for AI pipelines

Embedding jobs, index builds, and LLM evaluations are expensive in time and money. aimake’s job is to **skip work whose inputs have not changed** and **restore outputs** when the content-addressable cache already has the result.

The decision key is always a **fingerprint** — a SHA-256 digest — never file mtime alone.

## What goes into a fingerprint

For a typical command artifact, the hasher includes:

| Input | Effect when it changes |
|-------|------------------------|
| Declared `source` / `inputs` file bytes | Artifact becomes stale |
| Upstream dependency fingerprints | Cascades to dependents |
| `command` string | Rebuild even if data unchanged |
| `parameters` | Hyperparameter edits invalidate |
| Environment (names or values) | Per `environment_mode` |
| `external` provider / model / revision | Remote pin bumps invalidate |

Source-only artifacts (prompts, datasets) are fingerprinted from their content so dependents see edits immediately.

### What does *not* invalidate

- Touching a file to update mtime without changing bytes
- Reordering unrelated files on disk
- Volatile environment variables listed under `volatile_environment`
- External deps marked `volatile: true`

## Local cache layout

```text
.aimake/
├── state.db          # fingerprints + build metadata
├── cache/
│   └── <sha256>/     # content-addressable outputs
└── logs/
```

After a successful, validated run, outputs are copied into `.aimake/cache/<fingerprint>/`. The next plan that computes the same fingerprint can:

- **Reuse** if workspace outputs are already present, or
- **Restore** if the cache has the entry but the workspace outputs are missing (partial restore)

```bash
aimake cache status
aimake clean              # remove build outputs (cache kept)
aimake clean --all        # also clear .aimake/cache/
```

## Plan actions

```bash
aimake plan
```

| Action | Meaning |
|--------|---------|
| skip / reuse | Fingerprint matches; outputs present |
| restore | Cache hit; materialize outputs without re-running the command |
| run | No usable cache entry; execute `command` |

Cost estimates on `run` entries come from `cost_estimate` in YAML — they do not change the fingerprint, but they make plans actionable.

## Inspecting cache decisions

```bash
aimake status
aimake inspect evaluation
aimake explain evaluation
aimake explain evaluation --tree
aimake diff prompt --baseline stored
aimake diff dataset --baseline lock
```

Use `explain` when a step rebuilds unexpectedly. Use `diff` to see *what* changed in prompts, datasets, or models.

## Environment modes

```yaml
project:
  environment_mode: names   # default — safer with rotating secrets
  # environment_mode: values
```

- **names** — declaring `API_KEY` in `environment` ties the fingerprint to the presence of that variable name, not the secret value.
- **values** — fingerprint includes values; any secret rotation forces rebuilds (correct when the value truly affects outputs).

## External pins and probes

```yaml
external:
  - name: llm
    provider: openai
    model: gpt-4o
    revision: "2024-08"
    probe: true
    probe_mode: warn      # or invalidate
```

Bump `revision` when you intentionally change models. Enable probes so silent provider drift surfaces:

```bash
aimake probe
```

## Validation before cache write

Avoid caching bad outputs:

```yaml
validation:
  non_empty: true
  min_size_bytes: 10
  required_keys: [accuracy, cost_usd]
  revalidate_on_cache_hit: true
  command: python scripts/check_eval.py
```

With `atomic_outputs: true`, failed commands discard partial directories so incomplete trees never become the “current” outputs.

## Remote S3 cache

Share cache entries across machines:

```yaml
cache:
  remote:
    type: s3
    auto_pull: true
    auto_push: true
    team_id: acme
    s3:
      bucket: my-aimake-cache
      prefix: projects/my-rag-app/
      region: us-east-1
      # endpoint_url: https://minio.example.com
```

```bash
pip install "aimake[s3]"
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...

aimake cache remote-init --bucket my-org-cache --team acme --region us-east-1
aimake cache status
aimake cache push
aimake cache pull
aimake cache sync
```

Behavior:

- **`auto_pull`** — on build, missing local entries are fetched from S3 before deciding to run
- **`auto_push`** — after successful builds, new entries upload to S3
- **`team_id`** — namespaces shared prefixes so CI and laptops hit the same cache

S3-compatible endpoints (MinIO, etc.) work via `endpoint_url`.

More team workflows: [Remote & team cache](/docs/remote-cache).

## Lock files and `pull-lock`

After a green build, commit `aimake.lock`. It pins fingerprints (and remote identity in lock v2) so other environments reproduce the same cache keys:

```bash
aimake build
git add aimake.lock && git commit -m "Pin green fingerprints"

# On CI or a teammate's laptop
aimake cache pull-lock
aimake build              # should restore / reuse heavily
```

## CI patterns

### GitHub Actions cache of `.aimake`

The official action caches `.aimake` + `aimake.lock` between runs. See [CI/CD](/docs/ci-cd).

### Shared org bucket

Prefer remote S3 when runners are ephemeral and many jobs share work:

```yaml
- run: pip install "aimake[s3]"
- run: aimake cache pull-lock
- run: aimake build
- run: aimake cache push
```

## Performance tips

1. **Declare narrow inputs** — avoid fingerprinting huge unrelated trees.
2. **Split expensive stages** — smaller artifacts improve parallel restore and selective rebuilds.
3. **Provide `cost_estimate`** — teams skip accidental full rebuilds when `plan` shows a large bill.
4. **Keep prompts as source artifacts** — editing text should only invalidate downstream evals, not embeddings.
5. **Pin externals** — unpinned APIs cause mysterious “same YAML, different results” without cache invalidation.
6. **Commit `aimake.lock`** — aligns CI with local green builds.

## Related pages

- [How aimake works](/docs/how-it-works) — engine steps
- [Core concepts](/docs/concepts) — vocabulary
- [Remote & team cache](/docs/remote-cache) — team_id, remote-init
- [Writing aimake.yaml](/docs/configuration) — cache YAML reference
- [CLI reference](/docs/cli) — `aimake cache` subcommands
