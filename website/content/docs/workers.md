---
title: GPU & workers
description: Local GPU scheduling with resources.gpu, distributed SSH workers, and aimake workers status.
---

aimake can schedule GPU-hungry steps onto a local GPU pool and offload work to **SSH workers**. Fingerprinting and caching stay the same — only *where* the command runs changes.

See [CLI reference](/docs/cli#gpu--workers) for the `aimake workers` command.

## Local GPU scheduling

Declare how many GPUs the project owns (or leave auto-detect) and how many each artifact needs:

```yaml
project:
  name: my-rag-app
  gpus: 2                 # local GPUs (0 = auto-detect)

artifacts:
  embeddings:
    type: embedding
    depends_on: [processed]
    resources:
      gpu: 1
    command: python src/embed.py
    outputs:
      - build/embeddings/

  index:
    type: vector_index
    depends_on: [embeddings]
    resources:
      gpu: 0              # CPU-only
    command: python src/index.py
    outputs:
      - build/index/
```

### How scheduling works

- Artifacts with `resources.gpu > 0` wait until enough free GPUs are available.
- Independent GPU steps can run in parallel when the pool has capacity (`aimake build --jobs`).
- CPU-only steps (`gpu: 0` or omitted) do not reserve GPUs.
- Failed or finished steps release their GPU allocation for the next waiter.

| Field | Description |
|-------|-------------|
| `project.gpus` | Size of the local GPU pool (`0` = auto-detect) |
| `artifacts.*.resources.gpu` | GPUs required for that step |

Check the pool:

```bash
aimake workers
```

## Distributed SSH workers

Enable a worker pool and pin heavy artifacts to a named worker:

```yaml
workers:
  enabled: true
  workers:
    - name: gpu-node-1
      host: 10.0.0.5
      user: build
      gpus: 2
      jobs: 2
      workdir: /home/build/my-rag-app
      # ssh_options: ["-o", "StrictHostKeyChecking=no"]

artifacts:
  embeddings:
    type: embedding
    worker: gpu-node-1
    resources:
      gpu: 1
    command: python src/embed.py
    outputs:
      - build/embeddings/
```

### Worker fields

| Field | Description |
|-------|-------------|
| `workers.enabled` | Turn the pool on |
| `workers.workers[].name` | Unique worker id (referenced by `artifact.worker`) |
| `host` | SSH hostname or IP |
| `user` | SSH user (optional if implied by `~/.ssh/config`) |
| `gpus` | GPUs available on that host |
| `jobs` | Max concurrent jobs on that worker |
| `workdir` | Remote working directory for the project tree |
| `ssh_options` | Extra `ssh` flags |

Artifact field:

| Field | Description |
|-------|-------------|
| `artifacts.*.worker` | Name of the worker that should run this step |

Worker names must be unique. Aimake SSHs to the host, runs the artifact command in `workdir`, and brings results back into the local cache / outputs layout expected by the DAG.

## CLI

```bash
aimake workers
aimake workers -c path/to/aimake.yaml
```

Output summarizes:

- Local GPU capacity and current usage
- Each configured SSH worker (host, GPUs, jobs, reachability when checkable)

Use before a large build to confirm remotes are up:

```bash
aimake workers
aimake plan
aimake build --jobs 4
```

## Practical patterns

**Hybrid local + remote**

- Keep cheap CPU steps local.
- Pin `embeddings` / `train` to `gpu-node-1`.
- Leave evaluation on the laptop if it only needs API calls.

**Team cache + workers**

Workers produce the same fingerprints as local runs when inputs match. Pair with [remote cache](/docs/remote-cache) so CI can `pull-lock` instead of re-running GPU steps.

**Monorepo**

Workers are defined per `aimake.yaml`. Use `--project` / `-P` when inspecting or building a subproject:

```bash
aimake workers -c apps/rag/aimake.yaml
aimake build -P apps/rag
```

## Troubleshooting

| Symptom | Check |
|---------|--------|
| GPU steps serialize unexpectedly | `project.gpus` too low, or every step asks for `gpu: 1` on a 1-GPU box |
| Worker never used | `workers.enabled: true`, artifact `worker:` name matches, SSH keys work |
| Remote command fails | `workdir` path, synced code/data, env vars / [secrets](/docs/team#secrets) on the remote |
| Cache miss after remote run | Outputs not written to declared paths; run `aimake doctor` and `aimake inspect <artifact>` |

## Related

- [CLI reference](/docs/cli)
- [Remote & team cache](/docs/remote-cache)
- [Writing aimake.yaml](/docs/configuration)
- [Team & production](/docs/team)
