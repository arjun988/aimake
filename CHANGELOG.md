# Changelog

All notable changes to **aimake** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Persistent file-hash cache (SQLite) to skip re-hashing unchanged files
- Rich artifact diffs with stored snapshots (prompt unified diff, dataset row/sample diff, model parameter diff)
- S3 remote cache (`aimake cache push/pull/sync/status`)
- GPU-aware scheduling with `resources.gpu` per artifact
- Distributed workers via SSH (`workers` config, `aimake workers`)
- `aimake diff` command with `--baseline stored|lock|current`
- Artifact snapshots captured on every successful build
- Hardening test suite: force rebuild, targeted builds, corrupted cache, missing outputs, diff integration
- Experiment comparison (`aimake compare`) across build history
- Automatic hyperparameter optimization (`aimake optimize`) with grid/random search
- `aimake experiments list|show` for optimization run history
- `optimization` block in `aimake.yaml` (search_space, objective, parameter_artifact)
- Trial parameters injected as `AIMAKE_PARAM_*` environment variables during builds
- SQLite `experiments` and `experiment_trials` tables; build parameters stored per build
- Bayesian/Optuna search (`strategy: bayesian` / `optuna`, requires `aimake[optuna]`)
- Multi-objective Pareto optimization (`objective.metrics` + `directions`)
- Early stopping (`optimization.early_stopping`: patience, min_trials, min_delta)
- MLflow export (`optimization.mlflow`, requires `aimake[mlflow]`)

### Changed
- `Fingerprinter` uses persistent file-hash cache when `.aimake/state.db` is available
- Diff engine compares against stored snapshots, not just fingerprints

### Fixed
- File-hash cache invalidates correctly when file content changes in-process (size/mtime-aware memory cache)
- `compute_statuses()` auto-computes fingerprints when needed
- `plan()` supports `targets=` for subgraph planning

## [0.1.0] - 2026-09-01

### Added
- Initial release: incremental build system for AI/ML pipelines
- CLI: `init`, `build`, `plan`, `status`, `graph`, `clean`, `history`, `inspect`, `explain`, `doctor`, `eval`, `logs`
- Content-addressable local cache (SQLite + filesystem)
- SHA-256 fingerprinting for files, directories, and artifacts
- Dependency DAG with parallel execution (`--jobs`)
- AI artifact types: dataset, model, prompt, embedding, vector_index, evaluation, report
- Quality gates for CI (`aimake eval --check`)
- Git metadata in build history
- `aimake.lock` for logical reproducibility
- Example RAG pipeline in `examples/rag/`
- Python API: `Project.load()`, `.build()`, `.plan()`, `.explain()`
- Plugin interface (stub for future integrations)

### Fixed
- Thread-safe SQLite for parallel builds
- Windows-compatible cache atomic writes and console UTF-8 output

[Unreleased]: https://github.com/aimake/aimake/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/aimake/aimake/releases/tag/v0.1.0
