---
title: Interactive TUI
description: Full-screen Rich terminal UI for plan, build, and metrics — keyboard shortcuts and workflow for aimake tui.
---

`aimake tui` opens a lazygit-style full-screen console built on Rich Live: browse artifacts, replan, build all or selected targets, and inspect the last build’s metrics without leaving the terminal.

Requires an **interactive TTY**. In non-interactive CI, use `aimake plan` / `aimake build` instead (the TUI exits with a warning if stdin is not a TTY).

Related: [CLI reference](/docs/cli), [Python SDK](/docs/sdk-python), [How aimake works](/docs/how-it-works).

---

## Start

```bash
# from a project with aimake.yaml
aimake tui

# with global options
aimake --config path/to/aimake.yaml tui
aimake --project apps/rag tui
```

On start, the TUI refreshes statuses and computes a plan against `.aimake/state.db`.

---

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| **↑** / **↓** | Move selection among artifacts |
| **Enter** | Build the **selected** artifact (and its dependencies as needed) |
| **b** | Build **all** planned / stale work |
| **p** | **Replan** (recompute fingerprints and actions) |
| **r** | **Refresh** statuses from disk / state |
| **q** | Quit |

Help text is always shown in the UI footer:

```text
↑/↓ select   b build all   enter build selected   p replan   r refresh   q quit
```

---

## Layout and workflow

Typical loop:

1. Open `aimake tui` after editing a prompt or config
2. Glance at statuses (fresh / stale / missing) and the plan panel
3. Press **p** if you changed files while the TUI was open
4. **Enter** to rebuild one node, or **b** for the full incremental plan
5. Read the **Last build / metrics** panel (rebuilt / reused / failed counts, metric keys, git tip)
6. **q** when done

Builds run in a background worker thread so the Live display stays responsive; the status line shows busy/ready messages.

---

## When to use the TUI vs CLI

| Use TUI when… | Use CLI / SDK when… |
|---------------|---------------------|
| Local iteration on a laptop | CI, scripts, Docker without TTY |
| You want visual status + one-key rebuild | You need JSON (`aimake plan --format json`) |
| Exploring why nodes are stale | Automation / monorepo batch jobs |

For file-watch auto rebuilds without a full-screen UI, use `aimake watch` / `aimake watch --build`. For a browser UI, use the [dashboard](/docs/dashboard) with `aimake serve`.

---

## Troubleshooting

- **“requires an interactive TTY”** — run in a real terminal, not a piped subprocess.
- **Windows** — arrow keys and letters are supported via `msvcrt`; use Windows Terminal or a modern console host.
- **Stale selection after yaml edits** — press **r** or **p** to reload graph and plan.
- **Need cost before build** — prefer `aimake plan` (or the dashboard) if you need a detailed cost table; the TUI focuses on status + execute + metrics.
