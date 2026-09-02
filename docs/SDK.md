# aimake SDK

Use aimake from **Python scripts**, **TypeScript/CI**, or **Docker** — same mental model.

## Python

```python
from aimake.sdk import Aimake, load

# Context-manager style (recommended for CI)
with Aimake.load("aimake.yaml") as ai:
    plan = ai.plan()
    print(plan.to_run, plan.estimated_total_cost_usd)
    result = ai.build()
    assert result.success, result.failed

# Or classic Project API
from aimake import Project

project = Project.load("aimake.yaml")
project.build(targets=["evaluation"], jobs=4)
project.explain("evaluation", tree=True)
project.close()

# Monorepo
from aimake.sdk import load
proj = load(project="apps/rag")
```

### Common methods

| Method | Purpose |
|--------|---------|
| `plan(targets=None)` | What would run / restore / skip |
| `build(targets=None, force=..., dry_run=..., jobs=...)` | Execute incremental build |
| `status()` | Per-artifact status map |
| `explain(name)` | Why an artifact is stale |
| `doctor()` | Health checks |
| `compare_builds(a, b)` | Metric deltas |
| `registry_promote(...)` | Policy-gated promote |
| `repro_report(fmt="markdown")` | Reproducibility report |
| `export_lineage()` | OpenLineage / MLflow / W&B JSON |

## TypeScript

Talks to `aimake serve` (same API as the dashboard):

```bash
aimake serve --port 8765
```

```ts
import { Aimake } from "@aimake/sdk";

const ai = new Aimake({ baseUrl: process.env.AIMAKE_API });
const plan = await ai.plan();
const overview = await ai.overview();
```

Package: [`sdk/typescript`](../sdk/typescript).

| Concern | Python | TypeScript |
|---------|--------|------------|
| Load config / execute build | `Aimake.load().build()` | CLI / Docker / Python job; inspect via `ai.overview()` |
| Plan / graph / registry | In-process | HTTP client |
| CI image | `pip install aimake` or container | call API or `docker run … aimake build` |

## Docker

```bash
docker pull ghcr.io/arjun988/aimake:latest

docker run --rm -v "$PWD:/workspace" -w /workspace \
  ghcr.io/arjun988/aimake:latest build

docker run --rm -v "$PWD:/workspace" -w /workspace -p 8765:8765 \
  ghcr.io/arjun988/aimake:latest serve --host 0.0.0.0 --port 8765
```

GitHub Actions:

```yaml
- uses: docker://ghcr.io/arjun988/aimake:latest
  with:
    args: build
```

Or:

```yaml
- run: |
    docker run --rm -v "$PWD:/workspace" -w /workspace \
      ghcr.io/arjun988/aimake:latest doctor
    docker run --rm -v "$PWD:/workspace" -w /workspace \
      ghcr.io/arjun988/aimake:latest build
```

## Interactive TUI

```bash
aimake tui
```

Full-screen Rich UI: select artifacts, replan, build, view metrics (`↑/↓`, `b`, `enter`, `q`).

## See also

- [COMPARISON.md](COMPARISON.md)
- [ADAPTERS.md](ADAPTERS.md)
- Dashboard Developer page (when `aimake serve` + `npm run dev` are up)
