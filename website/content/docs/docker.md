---
title: Docker
description: Run aimake from ghcr.io/arjun988/aimake — docker run examples, serve the API, and GitHub Actions usage.
---

Official image: **`ghcr.io/arjun988/aimake`**

Published from the repo `Dockerfile` on pushes to the default branch and version tags (`v*`). Multi-stage build installs aimake with extras `s3`, `huggingface`, and `experiments` on Python 3.12-slim. Entrypoint is `aimake`.

This page is about **running aimake in a container**. To wrap *your* pipeline steps in images, use the [Docker plugin](/docs/plugins#docker-plugin) instead.

Related: [CI/CD](/docs/ci-cd), [TypeScript SDK](/docs/sdk-typescript) (`aimake serve`), [Python SDK](/docs/sdk-python).

---

## Pull

```bash
docker pull ghcr.io/arjun988/aimake:latest
```

Useful tags (from GHCR metadata): `latest`, semver (`2.0.0`, `2.0`), branch names, and short git SHAs.

---

## Run builds

Mount the project and set the working directory to `/workspace` (the image `WORKDIR`):

```bash
docker run --rm -v "$PWD:/workspace" -w /workspace \
  ghcr.io/arjun988/aimake:latest build

docker run --rm -v "$PWD:/workspace" -w /workspace \
  ghcr.io/arjun988/aimake:latest plan

docker run --rm -v "$PWD:/workspace" -w /workspace \
  ghcr.io/arjun988/aimake:latest doctor
```

Pass CLI args after the image name (entrypoint is already `aimake`):

```bash
docker run --rm -v "$PWD:/workspace" -w /workspace \
  ghcr.io/arjun988/aimake:latest build evaluation --jobs 4

docker run --rm -v "$PWD:/workspace" -w /workspace \
  ghcr.io/arjun988/aimake:latest --project apps/rag build
```

On Windows PowerShell, use `${PWD}` or an absolute path for the volume mount.

---

## Serve API / dashboard backend

```bash
docker run --rm -v "$PWD:/workspace" -w /workspace -p 8765:8765 \
  ghcr.io/arjun988/aimake:latest serve --host 0.0.0.0 --port 8765
```

Point the [dashboard](/docs/dashboard) or [`@aimake/sdk`](/docs/sdk-typescript) at `http://localhost:8765`.

---

## Environment and secrets

Forward tokens the same way you would locally:

```bash
docker run --rm \
  -v "$PWD:/workspace" -w /workspace \
  -e HF_TOKEN -e WANDB_API_KEY -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY \
  ghcr.io/arjun988/aimake:latest build
```

Do not bake secrets into the image. Prefer env / your secret store — see [Security](/docs/security).

---

## GitHub Actions

### Option A — docker URI action

```yaml
- uses: docker://ghcr.io/arjun988/aimake:latest
  with:
    args: build
```

### Option B — explicit docker run

```yaml
- name: aimake doctor + build
  run: |
    docker run --rm -v "$PWD:/workspace" -w /workspace \
      ghcr.io/arjun988/aimake:latest doctor
    docker run --rm -v "$PWD:/workspace" -w /workspace \
      ghcr.io/arjun988/aimake:latest build
```

### Option C — official composite Action

Prefer the first-party action when you want cache helpers and PR comments:

```yaml
- uses: arjun988/aimake/.github/actions/aimake@v2
  with:
    config: aimake.yaml
    extra: s3
```

See [CI/CD](/docs/ci-cd) for full workflows.

---

## Build the image locally

```bash
git clone https://github.com/arjun988/aimake
cd aimake
docker build -t aimake:local .
docker run --rm -v "$PWD:/workspace" -w /workspace aimake:local --help
```

Upstream publish workflow: [`.github/workflows/docker.yml`](https://github.com/arjun988/aimake/blob/main/.github/workflows/docker.yml) → `ghcr.io/<owner>/aimake`.

---

## Image vs Docker plugin

| | GHCR image | Docker plugin |
|--|------------|---------------|
| Purpose | Run **aimake** CLI/API | Run **artifact commands** inside your images |
| Config | `docker run … aimake …` | `plugins.docker` + `metadata.docker` |
| Docs | This page | [Plugins → Docker](/docs/plugins#docker-plugin) |
