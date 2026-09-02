---
title: CI/CD
description: Run aimake in GitHub Actions with quality gates, caching, the official composite action, and remote team cache patterns.
---

## Goals in CI

A solid aimake pipeline in continuous integration should:

1. Install a pinned Python (3.11+)
2. Restore prior fingerprints / cache when possible
3. **`aimake plan`** so reviewers see rebuild scope and estimated cost
4. **`aimake build`** incrementally
5. **`aimake eval --check`** against `quality_gates`
6. Fail the job when gates or builds fail

aimake is designed for this loop: content fingerprints behave well across checkout mtime noise, and locks + remote cache share work across runners.

## Minimal GitHub Actions workflow

```yaml
name: AI Build

on: [push, pull_request]

jobs:
  aimake:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install aimake
      - run: aimake doctor
      - run: aimake build
      - run: aimake eval --check
```

This matches the pattern in the project README. Expand it with caching and the official action for production use.

## Official GitHub Action

aimake ships a composite action at [`.github/actions/aimake`](https://github.com/arjun988/aimake/tree/main/.github/actions/aimake):

```yaml
- uses: arjun988/aimake/.github/actions/aimake@v1
  with:
    config: aimake.yaml
    post-comment: "true"
```

### Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `config` | `aimake.yaml` | Path to config |
| `targets` | `""` | Space-separated build targets |
| `python-version` | `3.11` | Python for setup-python |
| `extra` | `""` | pip extras, e.g. `s3` or `all` |
| `cache-path` | `.aimake` | Path cached by `actions/cache` |
| `post-comment` | `"true"` | Post PR summary comment |

### What it does

1. Sets up Python and installs `aimake` (with optional extras)
2. Restores `.aimake` + `aimake.lock` via `actions/cache`
3. Runs `aimake plan --format json` and records estimated cost
4. Runs `aimake build` (optional targets)
5. Runs `aimake eval --check` (non-blocking companion check in the action; still fail on build errors)
6. Writes a job summary and optional PR comment with rebuild count and cost

### Example with S3 extra

```yaml
- uses: arjun988/aimake/.github/actions/aimake@v1
  with:
    config: aimake.yaml
    extra: s3
    targets: evaluation report
    post-comment: "true"
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## Quality gates in CI

Declare thresholds in YAML:

```yaml
quality_gates:
  accuracy:
    minimum: 0.80
    required: true
  cost_usd:
    maximum: 1.00
    required: true
```

Then:

```bash
aimake eval --check
```

Exits non-zero when metrics fail or required metrics are missing. Keep gates next to the evaluation artifact’s `metrics.file` output.

## Caching strategies

### 1. actions/cache on `.aimake` (default in the official action)

Fast and free for single-repo CI. Keyed on `aimake.yaml` / lock hashes. Best when one workflow owns the cache.

### 2. Remote S3 team cache

Better when many workflows, machines, or repos share embeddings / indexes:

```bash
pip install "aimake[s3]"
aimake cache remote-init --bucket my-org-cache --team acme
aimake cache pull-lock
aimake build
aimake cache push
```

Commit `aimake.lock` from green main builds so PRs pull the same pins. See [Fingerprints & caching](/docs/caching) and [Remote & team cache](/docs/remote-cache).

### 3. Hybrid

Use `actions/cache` for warm local SQLite + layer S3 `auto_pull` / `auto_push` for cross-runner sharing.

## Recommended PR workflow

```yaml
name: aimake

on:
  pull_request:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write   # for PR comments
    steps:
      - uses: actions/checkout@v4
      - uses: arjun988/aimake/.github/actions/aimake@v1
        with:
          config: aimake.yaml
          post-comment: "true"
```

Reviewers see which steps will run and the estimated dollar cost before merge.

## Doctor and probes

Catch config issues early:

```bash
aimake doctor
aimake probe    # external model drift (when configured)
```

Wire `probe_mode: invalidate` only when you want CI to fail closed on provider drift; use `warn` while rolling out.

## Monorepos

```bash
aimake build --project=apps/rag
aimake eval --check --project=apps/rag
```

Point the action’s `config` at the subproject YAML, or set working-directory to the app folder.

## Secrets

Never commit API keys. Load them via GitHub Actions secrets and/or aimake `secrets:` providers. `aimake secrets` prints **names only**.

Ensure fingerprint `environment_mode` matches your intent so rotating CI secrets does not needlessly bust the entire cache (prefer `names` unless values affect outputs).

## Docker-based CI

```bash
docker pull ghcr.io/arjun988/aimake:latest
docker run --rm -v "$PWD:/workspace" -w /workspace \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY \
  ghcr.io/arjun988/aimake:latest build
```

See [Docker](/docs/docker).

## Checklist

- [ ] Python 3.11+
- [ ] `aimake.yaml` and example metrics paths exist in the repo
- [ ] `quality_gates` match what `eval --check` should enforce
- [ ] `aimake.lock` committed when using shared / remote cache
- [ ] Optional: official action with `post-comment: true`
- [ ] Optional: `aimake[s3]` + cloud credentials for team cache
- [ ] Optional: `aimake doctor` / `aimake probe` before build

## Related pages

- [Installation](/docs/installation) — extras for CI images
- [Quick start](/docs/quick-start) — local loop that mirrors CI
- [Fingerprints & caching](/docs/caching) — why mtimes do not break CI
- [Trust & reproducibility](/docs/trust) — repro / lineage in pipelines
- [CLI reference](/docs/cli) — `build`, `plan`, `eval`, `cache`
