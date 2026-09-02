# aimake vs DVC vs Make vs Prefect

Honest comparison for choosing a tool — or combining them.

## One-line summary

| Tool | Best for |
|------|----------|
| **aimake** | Incremental AI/ML pipelines — skip unchanged steps, show cost before run |
| **Make** | Generic file-based builds (C, docs, simple scripts) |
| **DVC** | Data and model **versioning** + ML experiments tied to Git |
| **Prefect / Airflow** | **Scheduling** and orchestration at scale |

aimake complements these tools; it does not replace a full orchestrator or a data registry.

---

## Feature matrix

| Capability | aimake | Make | DVC | Prefect | Airflow |
|------------|--------|------|-----|---------|---------|
| Incremental builds | ✅ Content fingerprints | ✅ File mtime | ⚠️ Stage-level | ❌ Flow reruns | ❌ Task reruns |
| AI artifact types | ✅ prompt, eval, embedding | ❌ | ⚠️ Generic stages | ❌ | ❌ |
| Cost estimate in plan | ✅ | ❌ | ❌ | ❌ | ❌ |
| Local dev UX | ✅ `plan` / `build` / `explain` | ✅ | ⚠️ | ✅ | ⚠️ |
| Data versioning | ⚠️ via DVC plugin | ❌ | ✅ | ❌ | ❌ |
| Cron / production scheduling | 🔜 | ❌ | ❌ | ✅ | ✅ |
| Distributed workers | ✅ SSH workers | ❌ | ❌ | ✅ | ✅ |
| DAG visualization | ✅ `aimake graph` | ❌ | ⚠️ | ✅ | ✅ |
| Remote cache | ✅ S3 | ❌ | ✅ remote storage | ❌ | ❌ |
| Hyperparameter search | ✅ built-in | ❌ | ⚠️ | ⚠️ | ⚠️ |

---

## When to use aimake

- You change **prompts, models, or configs** often and hate rerunning the whole pipeline
- You want **`aimake plan`** to show **cost and tokens** before spending
- Your pipeline is **local-first** (laptop + CI) with optional remote cache
- You need **quality gates** and **output validation** on eval artifacts

## When to use something else

- **DVC** — canonical dataset/model storage and Git-linked experiment reproduction
- **Prefect / Airflow** — nightly jobs, SLAs, retries across a cluster, observability at scale
- **Make** — simple non-AI builds with mature ecosystem and zero YAML schema

## Using together

```yaml
# aimake.yaml — incremental build
plugins:
  dvc:
    enabled: true

artifacts:
  dataset:
    metadata:
      dvc:
        tracked: true
```

```bash
aimake init --from=dvc    # migrate existing DVC pipeline
aimake build              # incremental + DVC pull/push
```

Prefect/Airflow can **trigger** `aimake build` as a single step instead of reimplementing incremental logic.

---

## Migration

```bash
aimake init --from=makefile
aimake init --from=dvc
aimake init --from=prefect
aimake init --from=airflow-dag
```

Review generated `aimake.yaml` before production use.

---

## FAQ

**Does aimake replace MLflow?**  
No. aimake builds artifacts incrementally; MLflow tracks experiments. Use both via `optimization.mlflow`.

**Does aimake replace Docker?**  
No. The Docker plugin wraps commands in containers; aimake decides *what* to run.

**Is aimake only for RAG?**  
No. Any DAG of datasets → transforms → models → evals → reports fits aimake.
