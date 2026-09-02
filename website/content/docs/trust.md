---
title: Trust & reproducibility
description: External probes, validation.command, SLSA-lite attestation, repro reports, partial RESTORE from cache, and lineage export (OpenLineage / MLflow / W&B).
---

aimake’s trust features catch silent drift, validate outputs, attest builds, restore missing files from cache without recompute, and export lineage. Use them when correctness matters as much as speed.

Related: [CLI reference](/docs/cli#trust--reproducibility), [Remote cache](/docs/remote-cache), [Dashboard](/docs/dashboard).

## External probes (`aimake probe`)

Pin remote models/APIs on artifacts and optionally **probe** live revisions:

```yaml
artifacts:
  answer:
    type: evaluation
    depends_on: [index, prompt]
    command: python src/eval.py
    outputs:
      - build/eval/metrics.json
    external:
      - name: llm
        provider: openai
        model: gpt-4o
        revision: "chatgpt-4o-latest-pin"
        probe: true
        probe_mode: warn        # or invalidate
        # probe_url: https://...  # optional HEAD/etag override
```

| Field | Description |
|-------|-------------|
| `name` | Logical dependency id |
| `provider` / `model` / `revision` | Pin included in fingerprints |
| `volatile` | If `true`, exclude from fingerprint (always “live”) |
| `probe` | Enable live drift check |
| `probe_mode` | `warn` (report only) or `invalidate` (treat as stale) |
| `probe_url` | Optional URL for HEAD / etag probing |

```bash
aimake probe
# OK: answer/llm: ok (revision…)
# or WARNING: answer/llm: DRIFT pinned=… live=…
# exit code 2 when drift detected
```

| Exit code | Meaning |
|-----------|---------|
| `0` | No drift (or no probeable deps) |
| `1` | Config / runtime error |
| `2` | Drift detected |

Run in CI before `aimake build` when you need to fail on provider drift. Dashboard **Repro** / API `/api/probe` expose the same findings.

## Output validation & `validation.command`

Structural checks catch empty or truncated outputs; a custom command covers semantic checks:

```yaml
artifacts:
  evaluation:
    type: evaluation
    command: python src/eval.py
    outputs:
      - build/eval/metrics.json
    validation:
      non_empty: true
      min_size_bytes: 32
      required_keys: [accuracy, cost_usd]
      min_value:
        accuracy: 0.5
      revalidate_on_cache_hit: true
      command: python scripts/check_eval.py
      timeout_seconds: 120
```

| Field | Description |
|-------|-------------|
| `non_empty` | Reject empty files |
| `min_size_bytes` | Minimum output size |
| `required_keys` | Required JSON keys |
| `min_rows` | Minimum rows for tabular outputs |
| `min_value` | Metric floors in JSON metrics |
| `revalidate_on_cache_hit` | Re-run checks when restoring from cache |
| `command` | Custom shell/Python check after structural validation |
| `timeout_seconds` | Timeout for `command` (default `120`) |

Failed validation discards bad outputs (with atomic staging) so a later build cannot “succeed” on garbage. See also quality gates via `aimake eval --check`.

## Attestation

Enable SLSA-lite provenance sidecars for successful artifact builds:

```yaml
attestation:
  enabled: true
  write_sidecars: true       # .aimake/attestations/
  embed_in_metadata: true
  include_environment: true
```

| Field | Description |
|-------|-------------|
| `enabled` | Write attestations on successful builds |
| `write_sidecars` | Persist under `.aimake/attestations/` |
| `embed_in_metadata` | Embed attestation summary in build metadata |
| `include_environment` | Include environment context |

```text
.aimake/attestations/
└── evaluation/
    └── latest.json
```

`aimake doctor` reports when attestation is enabled. `aimake repro` includes attestation status. Dashboard API: `/api/attestations`.

## Reproducibility report (`aimake repro`)

```bash
aimake repro
aimake repro --format markdown
aimake repro --format json -o reports/repro.json
aimake repro --format pdf
aimake repro -P apps/rag
```

| Option | Description |
|--------|-------------|
| `--format`, `-f` | `markdown` (default), `json`, or `pdf` |
| `--output`, `-o` | Destination path |
| `--project`, `-P` | Monorepo subproject |

Reports typically cover:

- Project / git metadata
- Artifact fingerprints vs `aimake.lock`
- Remote cache / `team_id` identity
- External probe / drift notes
- Attestation presence
- Environment fingerprint summary

Open the same view on the dashboard **Repro** page while `aimake serve` is running.

## Partial RESTORE from cache

When fingerprints match a **cache hit** but output files are missing (deleted `build/`, cleaned workspace, partial checkout), aimake plans **RESTORE** instead of a full rebuild:

```bash
rm -rf build/embeddings
aimake plan
# embeddings → RESTORE (from cache)
aimake build
# restores blobs without re-running the embedding command
```

| Action | Meaning |
|--------|---------|
| `SKIP` | Outputs present and fingerprint up to date |
| `RESTORE` | Fingerprint cached; materialize outputs from local/remote cache |
| `RUN` | Stale or missing — execute the command |

This pairs with [remote cache `pull-lock`](/docs/remote-cache): CI can pull pinned blobs and restore outputs without paying for GPU again. Revalidation (`revalidate_on_cache_hit`) still runs when configured.

## Lineage export

```yaml
lineage:
  enabled: true
  formats: [openlineage, mlflow]   # openlineage | mlflow | wandb
  auto_export_on_build: true
  output_dir: .aimake/lineage
```

```bash
aimake lineage
aimake lineage --format openlineage --format mlflow
aimake lineage -f wandb -o .aimake/lineage
```

| Option / field | Description |
|----------------|-------------|
| `--format`, `-f` | Repeatable: `openlineage`, `mlflow`, `wandb` |
| `--output-dir`, `-o` | Export directory |
| `auto_export_on_build` | Write lineage after successful builds |
| `output_dir` | Default `.aimake/lineage` |

| Format | Use |
|--------|-----|
| `openlineage` | OpenLineage-compatible job/run/dataset graph JSON |
| `mlflow` | MLflow-style run / artifact graph JSON |
| `wandb` | W&B-oriented graph JSON |

Dashboard **Lineage** page and `/api/lineage` visualize the same graph. For optimization-trial logging to a live MLflow server, see [Experiments — MLflow](/docs/experiments#mlflow-export).

## Combined trust config example

```yaml
attestation:
  enabled: true
lineage:
  enabled: true
  formats: [openlineage, mlflow]
  auto_export_on_build: true

artifacts:
  evaluation:
    type: evaluation
    command: python src/eval.py
    outputs: [build/eval/metrics.json]
    external:
      - name: llm
        provider: openai
        model: gpt-4o
        revision: "…"
        probe: true
        probe_mode: warn
    validation:
      non_empty: true
      required_keys: [accuracy]
      command: python scripts/check_eval.py
```

```bash
aimake probe
aimake build
aimake repro --format markdown
aimake lineage --format openlineage --format mlflow
```

## Related

- [CLI reference](/docs/cli)
- [Remote & team cache](/docs/remote-cache)
- [Team & production](/docs/team)
- [Dashboard](/docs/dashboard)
- [Security](/docs/security)
