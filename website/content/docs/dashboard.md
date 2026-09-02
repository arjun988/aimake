---
title: Dashboard
description: Run aimake serve with the Next.js dashboard on port 3000 — overview, graph, builds, experiments, registry, cache, settings, repro, lineage, and developer pages.
---

The aimake dashboard is a Next.js + Tailwind control plane for your pipeline. The **Python API** (`aimake serve`) reads your project; the **UI** on port **3000** renders graph, builds, experiments, registry, cache, trust, and settings.

Related: [CLI reference — serve](/docs/cli#aimake-serve), [Team](/docs/team), [Trust](/docs/trust), [Registry](/docs/registry).

## Architecture

```text
┌─────────────────────┐         ┌──────────────────────────┐
│  aimake serve       │  HTTP   │  Next.js dashboard       │
│  :8765  /api/*      │ ◄─────► │  :3000                   │
│  (project yaml/db)  │         │  NEXT_PUBLIC_AIMAKE_API  │
└─────────────────────┘         └──────────────────────────┘
```

| Process | Role | Default URL |
|---------|------|-------------|
| `aimake serve` | JSON API over the loaded project | `http://127.0.0.1:8765` |
| `npm run dev` (dashboard) | Web UI | `http://localhost:3000` |

`aimake graph --serve` starts the **same** API (useful for demos).

## Quick start

**Terminal 1 — API** (from your aimake project root):

```bash
aimake serve --port 8765
# or
aimake graph --serve --port 8765
```

| Option | Description |
|--------|-------------|
| `--host` | Bind host (default `127.0.0.1`) |
| `--port`, `-p` | API port (default `8765`) |
| `--open` | Open `http://localhost:3000` in a browser |
| `--config`, `-c` | Path to `aimake.yaml` |

**Terminal 2 — UI**:

```bash
cd dashboard
cp .env.local.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_AIMAKE_API` | `http://127.0.0.1:8765` | Dashboard API base URL |

Point this at a remote host if the API runs elsewhere (still bind carefully — prefer localhost or a reverse proxy).

## API surface

`aimake serve` announces the main endpoints. Common routes include:

| Endpoint | Used by |
|----------|---------|
| `/api/overview` | Overview |
| `/api/graph` | Graph |
| `/api/builds` | Builds |
| `/api/compare` | Experiments compare |
| `/api/experiments` | Experiments |
| `/api/registry` | Registry |
| `/api/cache` | Cache |
| `/api/settings` | Settings |
| `/api/policy/check` | Promote policy |
| `/api/repro` | Repro |
| `/api/lineage` | Lineage |
| `/api/attestations` | Attestations |
| `/api/probe` | External drift |
| `/api/developer` | Developer snippets |

Registry promote / tag and related POSTs are available for the UI (policy-gated like the CLI).

## Pages overview

### Overview (`/`)

Project health at a glance:

- Rebuild / skip / restore counts from the current plan
- Estimated cost and tokens when configured
- Recent build history highlights
- Quick links into graph and builds

### Graph (`/graph`)

Interactive dependency DAG with live artifact status (up to date, stale, changed). Use it to see blast radius before editing a prompt or dataset. Same data as `aimake graph --format json`.

### Builds (`/builds`)

Current build plan plus history from `.aimake/state.db` — counterpart to `aimake plan`, `aimake history`, and `aimake logs`.

### Experiments (`/experiments`)

Optimization trials and build compare (metric deltas) — UI for `aimake experiments list|show` and `aimake compare`. See [Experiments](/docs/experiments).

### Registry (`/registry`)

List versions, filter by stage/tag, **promote** (with `policy.promote` checks), **tag**, and **remote push** when `registry.remote` is configured. See [Artifact registry](/docs/registry).

### Cache (`/cache`)

Local cache size/entries, remote S3 configuration, and **team** prefix (`team_id`). Pair with [Remote & team cache](/docs/remote-cache).

### Settings (`/settings`)

Live view of production wiring:

- Notifications (Slack / Discord / email flags)
- Secrets providers loaded (keys only)
- Promote policy summary
- Attestation / lineage toggles

Use alongside `aimake notify-test`, `aimake secrets`, and yaml under [Team & production](/docs/team).

### Repro (`/repro`)

Fingerprints vs lock, git metadata, external drift, attestations — the visual form of `aimake repro`. See [Trust](/docs/trust).

### Lineage (`/lineage`)

OpenLineage / MLflow / W&B-style artifact graph from exports under `.aimake/lineage` (or on-demand API). See [Trust — lineage](/docs/trust#lineage-export).

### Developer (`/developer`)

SDK snippets (Python / TypeScript), Docker image hints, and TUI keyboard notes — useful onboarding for the [Python SDK](/docs/sdk-python), [TypeScript SDK](/docs/sdk-typescript), [Docker](/docs/docker), and [Interactive TUI](/docs/tui).

## Production UI build

```bash
cd dashboard
npm run build
npm start
```

Keep `aimake serve` running (or reverse-proxy `/api/*` to it). Example nginx sketch:

```nginx
location /api/ {
  proxy_pass http://127.0.0.1:8765;
}
```

## Design notes

- Dark navy sidebar + light content canvas
- Theme toggle (persisted in `localStorage`)
- Plus Jakarta Sans + IBM Plex Mono
- Flat panels and metric cards — no decorative mesh/glow

Details live in `dashboard/README.md`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| UI empty / network errors | Confirm `aimake serve` is up; match `NEXT_PUBLIC_AIMAKE_API` |
| Wrong project | Restart `serve` from the correct root or pass `--config` |
| Promote blocked | Check `policy.promote` and approval env; same as CLI |
| No lineage / repro data | Run `aimake lineage` / `aimake repro` or enable auto-export / attestation |

## Related

- [CLI reference](/docs/cli)
- [Remote & team cache](/docs/remote-cache)
- [Experiments](/docs/experiments)
- [Artifact registry](/docs/registry)
- [Trust & reproducibility](/docs/trust)
- [Team & production](/docs/team)
