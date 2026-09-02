---
title: TypeScript SDK
description: "@aimake/sdk HTTP client for aimake serve — plan, graph, registry, lineage, and dashboard APIs from Node or CI."
---

`@aimake/sdk` is an HTTP client for [`aimake serve`](/docs/dashboard) — the same JSON API the web dashboard uses. It is the **control plane**: inspect plans, graphs, builds, registry, lineage, and promote. **Builds still execute** in the Python process (CLI, [Python SDK](/docs/sdk-python), or [Docker](/docs/docker)).

Related: [Dashboard](/docs/dashboard), [Python SDK](/docs/sdk-python), [CI/CD](/docs/ci-cd).

---

## Prerequisites

1. Aimake project with `aimake.yaml`
2. API server:

```bash
aimake serve --port 8765
# or
aimake serve --host 0.0.0.0 --port 8765
```

3. Package from the monorepo:

```bash
cd sdk/typescript
npm install
npm run build
# optional: npm link
```

Set `AIMAKE_API` (or pass `baseUrl`) to the serve URL. Default base URL is `http://127.0.0.1:8765`.

---

## Usage

```ts
import { Aimake } from "@aimake/sdk";

const ai = new Aimake({
  baseUrl: process.env.AIMAKE_API ?? "http://127.0.0.1:8765",
});

await ai.health();
const plan = await ai.plan();
const overview = await ai.overview();
const lineage = await ai.lineage();

console.log(plan.to_run, overview.stats);
```

Errors raise `AimakeError` with HTTP `status` and optional `body`.

---

## API surface

| Method | HTTP | Mirrors |
|--------|------|---------|
| `health()` | `GET /api/health` | Lightweight ping |
| `overview()` | `GET /api/overview` | Project + plan + statuses + recent builds |
| `plan()` | `GET /api/plan` | `Project.plan()` |
| `graph()` | `GET /api/graph` | Dependency graph / DOT |
| `builds(limit?)` | `GET /api/builds` | Build history |
| `lineage()` | `GET /api/lineage` | Lineage graph |
| `repro()` | `GET /api/repro` | Reproducibility payload |
| `settings()` | `GET /api/settings` | Config summary (no secret values) |
| `cache()` | `GET /api/cache` | Cache / team status |
| `registry({ artifact, stage })` | `GET /api/registry` | Registry entries |
| `promote(artifact, version, stage, opts?)` | `POST /api/registry/promote` | Policy-gated promote |

Example promote:

```ts
await ai.promote("evaluation", "v3", "production", { force: false });
```

Policy gates are enforced server-side — see [Security](/docs/security).

---

## Python vs TypeScript

| Concern | Python (`aimake.sdk`) | TypeScript (`@aimake/sdk`) |
|---------|----------------------|----------------------------|
| Load config / execute build | `Aimake.load().build()` | CLI / Docker / Python job; inspect via `overview()` / `builds()` |
| Plan / graph / registry | In-process | HTTP client |
| CI image | `pip install aimake` or container | Call API **or** `docker run … aimake build` |
| Lineage / repro | `export_lineage()` / `repro_report()` | `lineage()` / `repro()` |

---

## Typical architecture

```text
┌─────────────────┐     HTTP      ┌──────────────────┐
│  Node / CI / UI │ ────────────► │  aimake serve     │
│  @aimake/sdk    │               │  (Python project) │
└─────────────────┘               └────────┬─────────┘
                                           │
                                           ▼
                                  aimake build / cache / registry
```

Run serve next to the project root (or mount it in Docker):

```bash
docker run --rm -v "$PWD:/workspace" -w /workspace -p 8765:8765 \
  ghcr.io/arjun988/aimake:latest serve --host 0.0.0.0 --port 8765
```

Then point the TS client at `http://localhost:8765`.

---

## Package location

Source and README: [`sdk/typescript`](https://github.com/arjun988/aimake/tree/main/sdk/typescript) on GitHub.
