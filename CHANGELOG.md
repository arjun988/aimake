# Changelog

All notable changes to **aimake** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/arjun988/aimake/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/arjun988/aimake/releases/tag/v1.0.0
[0.1.0]: https://github.com/arjun988/aimake/releases/tag/v0.1.0
