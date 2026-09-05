# aimake for VS Code / Cursor

Incremental AI pipeline builds in the sidebar — see what's stale, rebuild targets, and inspect cost estimates without leaving the editor.

## Requirements

- [VS Code](https://code.visualstudio.com/) or [Cursor](https://cursor.com/) `^1.85.0`
- Python package: `pip install aimake`
- A project with `aimake.yaml` at the workspace root (or nested; the extension discovers it)

## Install (development)

```bash
cd extension
npm install
npm run compile
```

Then press **F5** ("Run Extension") to open an Extension Development Host with aimake loaded.

### Package a `.vsix`

```bash
npm install -g @vscode/vsce
cd extension
vsce package
```

Install the generated `aimake-*.vsix` via **Extensions: Install from VSIX…**.

## Features

- **Plan tree** in the activity bar — groups: *To rebuild* / *Reuse* / *Restore*
- **Status bar** — `aimake · N stale · ~$X.XX`
- **Commands**
  - Refresh Plan
  - Build All / Build Stale / Build Target
  - Explain Target (markdown preview or output channel)
  - Open Config (`aimake.yaml`)
  - Doctor
  - Show Cost Estimate
- **Auto-refresh** when `aimake.yaml` (and common sources) change
- Click a stale (RUN) artifact to rebuild that target; context menu for Explain

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `aimake.cliPath` | `aimake` | CLI path. Auto-detects nearby `venv` / `.venv` if not on PATH |
| `aimake.configPath` | *(empty)* | Optional path to `aimake.yaml` |
| `aimake.autoRefresh` | `true` | Refresh plan on file changes |
| `aimake.project` | *(empty)* | Monorepo project (`-P`) |

## Troubleshooting

**Status bar shows `aimake · error` / “CLI not found”**

The Extension Host often does **not** inherit your activated venv PATH. Fixes:

1. Reload the Extension Host after this update (auto-finds `../venv/Scripts/aimake.exe` when opening `examples/rag`), or
2. Set **Settings → aimake: Cli Path** to the full path, e.g.  
   `C:\Users\...\aimake\venv\Scripts\aimake.exe`
3. Or `pip install aimake` into a Python that is on your system PATH

## CLI used

```bash
aimake plan --format json
aimake explain <target> --format json
aimake build [targets...]
aimake doctor
```
