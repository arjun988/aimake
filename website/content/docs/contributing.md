---
title: Contributing
description: Develop aimake locally — editable install, extras, pytest, project layout, and how to propose changes.
---

Contributions are welcome — bug fixes, docs, plugins, and features from the [IMPROVE.md](https://github.com/arjun988/aimake/blob/main/IMPROVE.md) roadmap. Open an issue or pull request on [GitHub](https://github.com/arjun988/aimake).

Related: [Architecture](/docs/architecture), [Changelog](/docs/changelog), [Security](/docs/security).

---

## Requirements

- Python **3.11+**
- Git
- Optional: Docker (plugin / image tests), Node 18+ (dashboard / docs website)

---

## Clone and editable install

```bash
git clone https://github.com/arjun988/aimake.git
cd aimake

# recommended for contributors — all extras + pytest
pip install -e ".[all]"

# or narrower
pip install -e ".[dev]"                 # pytest, coverage
pip install -e ".[dev,s3,plugins]"      # common combo
```

Confirm the CLI:

```bash
aimake --version
aimake doctor
```

Extras defined in `pyproject.toml`: `dev`, `s3`, `huggingface`, `wandb`, `dvc`, `plugins`, `optuna`, `mlflow`, `experiments`, `all`.

---

## Run tests

```bash
pytest tests/ -v

# with coverage (dev extra)
pytest tests/ --cov=aimake --cov-report=term-missing
```

`pyproject.toml` sets `testpaths = ["tests"]` and `pythonpath = ["."]`.

Focus a area:

```bash
pytest tests/test_plugins.py -v
pytest tests/test_sdk_tui.py -v
```

---

## Project layout (for PRs)

| Path | Role |
|------|------|
| `aimake/` | Library + CLI |
| `tests/` | Pytest suite |
| `examples/` | Sample pipelines (e.g. RAG) |
| `dashboard/` | Next.js UI (pairs with `aimake serve`) |
| `website/` | Public docs site (this content) |
| `sdk/typescript/` | `@aimake/sdk` |
| `docs/` | Short reference markdown (ADAPTERS, COMPARISON, SDK) |
| `.github/actions/aimake` | Composite GitHub Action |
| `Dockerfile` | GHCR image |

See [Architecture](/docs/architecture) for package responsibilities.

---

## Docs website (local)

```bash
cd website
npm install
npm run dev          # http://localhost:3001
```

Doc pages live in `website/content/docs/*.md` with YAML frontmatter (`title`, `description`). Nav order is `website/lib/nav.ts`.

---

## Dashboard (optional)

```bash
# terminal 1
aimake serve --port 8765

# terminal 2
cd dashboard
npm install
npm run dev
```

---

## Coding guidelines

- Match existing style in the module you touch (Typer CLI, Pydantic config, Rich UI)
- Prefer extending schema in `aimake/config/schema.py` over ad-hoc dicts
- Add tests for new CLI flags, planner behavior, and plugins
- Do not commit secrets, `.env`, or large cache blobs
- Update [CHANGELOG.md](https://github.com/arjun988/aimake/blob/main/CHANGELOG.md) for user-visible changes
- For roadmap items, mention the IMPROVE number in the PR (e.g. “Implements #8: aimake watch”)

---

## Suggesting features

1. Check [IMPROVE.md](https://github.com/arjun988/aimake/blob/main/IMPROVE.md) and existing issues
2. Open an issue with use case + proposed CLI/yaml shape
3. For large designs, start with a draft PR or discussion before a full implementation

---

## License

Contributions are under the project’s **Apache License 2.0**.
