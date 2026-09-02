# @aimake/sdk

TypeScript client for [`aimake serve`](../../README.md). Mirrors the Python `Project` / `aimake.sdk` API for CI scripts and internal tools.

## Install

```bash
# from monorepo
cd sdk/typescript && npm install && npm run build

# or link locally
npm link
```

Requires a running API:

```bash
aimake serve --port 8765
```

## Usage

```ts
import { Aimake } from "@aimake/sdk";

const ai = new Aimake({ baseUrl: "http://127.0.0.1:8765" });

await ai.health();
const plan = await ai.plan();
const overview = await ai.overview();
const lineage = await ai.lineage();

console.log(plan.to_run, overview.stats);
```

## Python parity

| Python (`aimake.sdk`) | TypeScript (`@aimake/sdk`) |
|-----------------------|----------------------------|
| `Aimake.load(...).plan()` | `ai.plan()` |
| `Aimake.load(...).build()` | run via CLI/container; status via `ai.overview()` / `ai.builds()` |
| `project.graph_dict()` | `ai.graph()` |
| `project.lineage_graph()` | `ai.lineage()` |
| `project.repro_report()` | `ai.repro()` |
| `project.registry_list()` | `ai.registry()` |
| `project.registry_promote()` | `ai.promote()` |

Builds execute in the project process (Python/`aimake` CLI/Docker). The TS SDK is the control-plane client over HTTP — same surface the dashboard uses.

See [docs/SDK.md](../../docs/SDK.md).
