# aimake Dashboard

Professional Next.js + Tailwind control plane for aimake pipelines.

## Features

- **Overview** — project health, rebuild count, estimated cost, recent builds
- **Graph** — interactive dependency DAG with live artifact status
- **Lineage** — OpenLineage / MLflow / W&B style artifact graph
- **Builds** — current plan + build history
- **Experiments** — trial list + build compare (metric deltas)
- **Registry** — list versions, promote (policy-gated), tag, remote push
- **Cache** — local / remote / team cache status
- **Repro** — fingerprints, git, drift, attestations
- **Developer** — Python/TS SDK snippets, Docker image, TUI keys
- **Settings** — notifications, secrets, policy, attestation, lineage

## Prerequisites

1. Python aimake API running against your project
2. Node.js 18+

## Run

Terminal 1 — API (from your aimake project root):

```bash
aimake serve --port 8765
# or
aimake graph --serve --port 8765
```

Terminal 2 — UI:

```bash
cd dashboard
cp .env.local.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_AIMAKE_API` | `http://127.0.0.1:8765` | Dashboard API base URL |

## Design

- **Layout:** dark navy sidebar + light content canvas (Razorpay / Stripe Dashboard pattern)
- **Light:** `#F5F7FB` page, white panels, electric blue `#1A73E8`
- **Dark:** charcoal surfaces, same blue accent — no gradients, glow, or mesh
- Plus Jakarta Sans + IBM Plex Mono
- Theme toggle in the top bar (persisted in `localStorage`)
- Flat panels, 1px borders, left accent on metric cards

## Production build

```bash
npm run build
npm start
```

Keep `aimake serve` running (or reverse-proxy `/api/*` to it).
