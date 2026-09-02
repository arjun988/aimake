---
title: Installation
description: Install aimake from PyPI or pipx, optional extras (s3, huggingface, wandb, and more), and verify your setup.
---

## Requirements

- **Python 3.11+**
- A shell where `pip` (or `pipx`) can install packages
- Optional: Docker CLI, Ollama, cloud credentials for remote cache / plugins

aimake is published on [PyPI](https://pypi.org/project/aimake/) as the package name **`aimake`**. Source: [github.com/arjun988/aimake](https://github.com/arjun988/aimake).

## Install from PyPI

```bash
pip install aimake
```

Verify:

```bash
aimake --version
# or
aimake -V
```

You should see a version in the **1.7.x** line (or newer).

## Isolated CLI with pipx

If you want the CLI available globally without polluting a project venv:

```bash
pipx install aimake
aimake --version
```

Still use a project virtualenv for your pipeline scripts (`python src/evaluate.py`); pipx only isolates the `aimake` entry point.

## Optional extras

Core aimake works out of the box. Extras unlock remotes, plugins, and experiment tooling:

| Extra | Install | Enables |
|-------|---------|---------|
| `s3` | `pip install aimake[s3]` | S3 remote cache (`boto3`) |
| `huggingface` | `pip install aimake[huggingface]` | `aimake hf` commands |
| `wandb` | `pip install aimake[wandb]` | Weights & Biases logging |
| `dvc` | `pip install aimake[dvc]` | DVC pull/push (`dvc` CLI) |
| `plugins` | `pip install aimake[plugins]` | HF + W&B + DVC |
| `optuna` | `pip install aimake[optuna]` | Bayesian / Optuna optimization |
| `mlflow` | `pip install aimake[mlflow]` | MLflow trial export |
| `experiments` | `pip install aimake[experiments]` | Optuna + MLflow |
| `all` | `pip install aimake[all]` | Everything above + common tooling |
| `dev` | `pip install aimake[dev]` | pytest, coverage |

Examples:

```bash
# Shared team cache on S3
pip install "aimake[s3]"

# Hyperparameter search + MLflow
pip install "aimake[experiments]"

# Full developer install
pip install "aimake[all]"
```

### Tools that are not pip extras

| Tool | How to get it | Used for |
|------|---------------|----------|
| **Docker** | Docker Desktop / Docker Engine CLI | [Docker plugin](/docs/plugins) — containerized artifact commands |
| **Ollama** | [ollama.com](https://ollama.com/) | Local LLM model pull via `aimake ollama` |

## Install from source (contributors)

```bash
git clone https://github.com/arjun988/aimake
cd aimake
pip install -e ".[all]"
pytest tests/ -v
```

## Official Docker image

For CI or locked environments without a local Python install:

```bash
docker pull ghcr.io/arjun988/aimake:latest
docker run --rm -v "$PWD:/workspace" -w /workspace ghcr.io/arjun988/aimake:latest build
```

More detail: [Docker](/docs/docker).

## Project layout after install

Installing the package does not create a project. Initialize one:

```bash
mkdir my-rag && cd my-rag
aimake init
```

That scaffolds `aimake.yaml` and `.aimake/`. See [Quick start](/docs/quick-start).

## Health check

Once you have a config file:

```bash
aimake doctor
```

`doctor` checks project layout, config sanity, and common setup issues before you spend time on a full build.

## Troubleshooting

### `aimake` not found after pip install

- Confirm the same Python is on your `PATH` that you installed into (`python -m pip install aimake`, then `python -m aimake --version` if needed).
- On Windows, ensure the Scripts directory is on `PATH`, or use a virtual environment and activate it.

### Wrong Python version

aimake requires **3.11+**. Check with:

```bash
python --version
```

### Optional import errors

If a command mentions missing `boto3`, `optuna`, or similar, install the matching extra:

```bash
pip install "aimake[s3]"
pip install "aimake[optuna]"
```

## Next steps

- [Quick start](/docs/quick-start) — first plan and build
- [Writing aimake.yaml](/docs/configuration) — declare your DAG
- [CI/CD](/docs/ci-cd) — GitHub Actions and quality gates
