---
title: VS Code / Cursor extension
description: Sidebar plan with stale steps, rebuild targets, and cost estimates inside the editor.
---

The official **aimake** extension brings plan, cost, and rebuild into VS Code and Cursor so you do not leave the editor to see what is stale.

## Features

- **Activity bar → aimake → Plan** — groups artifacts into *To rebuild*, *Reuse*, and *Restore*
- **Status bar** — `aimake · N stale · ~$X.XX` (click for a cost summary)
- **Build All / Build Stale / Build Target** — runs the CLI with progress notifications
- **Explain Target** — root cause, fingerprints, and dependency tree (markdown preview or Output channel)
- **Open Config** — jump to `aimake.yaml`
- **Doctor** — project health checks in the Output channel
- **Auto-refresh** when `aimake.yaml` or common sources (`prompts/`, `data/`, `src/`, …) are saved

## Requirements

1. Install the Python CLI: `pip install aimake`
2. Open a workspace that contains `aimake.yaml` (root or nested)

## Install (development)

From the aimake repository:

```bash
cd extension
npm install
npm run compile
```

Press **F5** (“Run Extension”) to launch an Extension Development Host.

### Package a `.vsix`

```bash
npm install -g @vscode/vsce
cd extension
vsce package
```

Then **Extensions: Install from VSIX…** and pick `aimake-0.1.0.vsix`.

Marketplace publish (when ready): `vsce publish` with a publisher account.

## Commands

| Command | What it does |
|---------|----------------|
| `aimake: Refresh Plan` | Re-run `aimake plan --format json` |
| `aimake: Build All` | `aimake build` |
| `aimake: Build Stale` | Build only `to_run` targets from the current plan |
| `aimake: Build Target` | Build one artifact (tree click / context menu) |
| `aimake: Explain Target` | `aimake explain <name> --format json` |
| `aimake: Open Config` | Open `aimake.yaml` |
| `aimake: Doctor` | `aimake doctor` |
| `aimake: Show Cost Estimate` | Toast with totals |

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `aimake.cliPath` | `aimake` | CLI executable |
| `aimake.configPath` | *(empty)* | Optional path to `aimake.yaml` |
| `aimake.autoRefresh` | `true` | Refresh plan on relevant file saves |
| `aimake.project` | *(empty)* | Monorepo `-P` / `--project` |

## How it talks to aimake

The extension shells out to the CLI (same JSON the CI and dashboard use):

```bash
aimake plan --format json
aimake explain <target> --format json
aimake build [targets...]
aimake doctor
```

Source lives in [`extension/`](https://github.com/arjun988/aimake/tree/main/extension) on GitHub.

## Related

- [CLI reference](/docs/cli)
- [Interactive TUI](/docs/tui)
- [Dashboard](/docs/dashboard)
- [Quick start](/docs/quick-start)
