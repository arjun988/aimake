# Changelog

All notable changes to **aimake** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.4.0] - 2026-09-02

### Added
- Web dashboard (Next.js + Tailwind) in `dashboard/` — overview, graph, builds, experiments, registry, cache
- `aimake serve` — JSON API for the dashboard (`/api/overview`, `/api/graph`, `/api/builds`, `/api/compare`, `/api/experiments`, `/api/registry`, `/api/cache`)
- `aimake graph --serve` — start the same API for demos
- Registry promote / tag via dashboard POST endpoints

## [1.3.0] - 2026-09-02

### Added
- `aimake init --from` generators: `makefile`, `dvc`, `prefect`, `airflow-dag`
- Official GitHub Action (`.github/actions/aimake`) with cache, plan JSON, PR comments
- `aimake watch` — poll inputs and re-plan / optional auto-build
- `aimake explain --tree` and `--format json` with cost, validation, external deps
- `aimake plan --format json` for CI integrations
- [docs/COMPARISON.md](docs/COMPARISON.md) and [docs/ADAPTERS.md](docs/ADAPTERS.md)

## [1.2.0] - 2026-09-02

### Added
- External dependencies (`external` on artifacts): pin provider/model/revision; `volatile: true` to opt out
- Environment fingerprint modes: `environment_mode: names|values`, `volatile_environment` list
- Atomic outputs: stage → validate → promote; discard partial outputs on failure
- `aimake.utils.resolve_output()` helper for staged artifact writes
- Output validation (`validation` block): size, non-empty, required JSON keys, min metric values
- Revalidation on cache hit catches silent garbage outputs with valid fingerprints
- Plan cost estimates: `cost_estimate` per artifact; `aimake plan` shows `$` and tokens for stale steps
- Quality gates: `required: true` fails when metric is missing

### Changed
- Default env fingerprinting uses variable names only (not live values)
- Failed builds remove partial outputs instead of leaving corrupt artifacts

## [1.1.0] - 2026-09-01

### Added
- Weights & Biases plugin (`plugins.wandb`, `aimake wandb sync/status`)
- DVC plugin (`plugins.dvc`, `aimake dvc pull/push/status`)
- Docker plugin (`plugins.docker`, `aimake docker build/status`, command wrapping)
- Ollama plugin (`plugins.ollama`, `aimake ollama pull/status`)
- Optional extras: `wandb`, `dvc`, `plugins`; updated `all` extra
- Plugin tests (`tests/test_plugins.py`, 101 total tests)

### Changed
- `PluginManager.wrap_command()` for Docker command rewriting during builds
- Build runner pre-pulls DVC data and Ollama models before planning
- README: full plugin docs, updated CLI reference and roadmap
- PyPI project URLs point to `github.com/arjun988/aimake`

## [1.0.0] - 2026-09-01

### Added
- Persistent file-hash cache (SQLite) to skip re-hashing unchanged files
- Rich artifact diffs with stored snapshots (prompt unified diff, dataset row/sample diff, model parameter diff)
- S3 remote cache (`aimake cache push/pull/sync/status`)
- GPU-aware scheduling with `resources.gpu` per artifact
- Distributed workers via SSH (`workers` config, `aimake workers`)
- `aimake diff` command with `--baseline stored|lock|current`
- Artifact snapshots captured on every successful build
- Experiment comparison (`aimake compare`) across build history
- Automatic hyperparameter optimization (`aimake optimize`) with grid/random/Bayesian search
- `aimake experiments list|show` for optimization run history
- `optimization` block in `aimake.yaml` (search_space, objective, parameter_artifact)
- Trial parameters injected as `AIMAKE_PARAM_*` environment variables during builds
- Bayesian/Optuna search, multi-objective Pareto, early stopping, MLflow export
- Hugging Face Hub plugin (`plugins.huggingface`, `aimake hf pull/push/status`)
- Versioned artifact registry (`registry` config, `aimake registry list/show/promote/tag`)
- Hyperband and successive-halving pruning with Optuna multi-fidelity support
- Hardening test suite (91 tests)

### Changed
- `Fingerprinter` uses persistent file-hash cache when `.aimake/state.db` is available
- Diff engine compares against stored snapshots, not just fingerprints
- `compute_statuses()` auto-computes fingerprints when needed
- `plan()` supports `targets=` for subgraph planning

### Fixed
- File-hash cache invalidates correctly on in-process content changes
- CLI history table handles normalized build rows
- Console helpers for workers, registry, and optimization output

## [0.1.0] - 2026-09-01

### Added
- Initial release: incremental build system for AI/ML pipelines
- CLI: `init`, `build`, `plan`, `status`, `graph`, `clean`, `history`, `inspect`, `explain`, `doctor`, `eval`, `logs`
- Content-addressable local cache (SQLite + filesystem)
- SHA-256 fingerprinting, dependency DAG, parallel execution
- AI artifact types: dataset, model, prompt, embedding, vector_index, evaluation, report
- Quality gates for CI (`aimake eval --check`)
- Git metadata in build history, `aimake.lock` for logical reproducibility
- Example RAG pipeline in `examples/rag/`
- Python API: `Project.load()`, `.build()`, `.plan()`, `.explain()`

### Fixed
- Thread-safe SQLite for parallel builds
- Windows-compatible cache atomic writes and console UTF-8 output

[Unreleased]: https://github.com/arjun988/aimake/compare/v1.4.0...HEAD
[1.4.0]: https://github.com/arjun988/aimake/releases/tag/v1.4.0
[1.3.0]: https://github.com/arjun988/aimake/releases/tag/v1.3.0
[1.2.0]: https://github.com/arjun988/aimake/releases/tag/v1.2.0
[1.1.0]: https://github.com/arjun988/aimake/releases/tag/v1.1.0
[1.0.0]: https://github.com/arjun988/aimake/releases/tag/v1.0.0
[0.1.0]: https://github.com/arjun988/aimake/releases/tag/v0.1.0
