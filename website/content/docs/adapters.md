---
title: Framework adapters
description: Wrap LangChain, LlamaIndex, and Hugging Face Transformers pipelines as aimake artifacts with fingerprints, validation, and incremental builds.
---

aimake does not replace LangChain, LlamaIndex, or Transformers. It **wraps** the scripts you already run as DAG nodes so unchanged prompts, indexes, and models are skipped — with cost estimates, validation, and cache restore.

Pattern for every adapter:

1. Declare an artifact in `aimake.yaml` (`depends_on`, `command`, `outputs`, optional `external` / `validation`)
2. Keep framework code in a normal Python entrypoint
3. Write outputs via `aimake.utils.outputs.resolve_output()` so atomic promote works
4. Run `aimake plan` / `aimake build` (or [watch](/docs/cli) while iterating)

See also: [Plugins](/docs/plugins), [Configuration](/docs/configuration), [Fingerprints & caching](/docs/caching).

---

## LangChain

Treat a chain (prompt → model → metrics) as an `evaluation` (or `report`) artifact. Pin the chat model with `external` so provider-side model swaps can invalidate the fingerprint.

```yaml
artifacts:
  chain:
    type: evaluation
    depends_on: [prompt, index]
    command: python src/run_chain.py
    outputs:
      - build/chain/
    metrics:
      file: build/chain/metrics.json
    external:
      - name: chat-model
        provider: openai
        model: gpt-4o-mini
        revision: "2024-07"
    validation:
      required_keys: [accuracy, cost_usd]
      non_empty: true
```

```python
# src/run_chain.py
import json
import os
from aimake.utils.outputs import resolve_output

# from langchain_openai import ChatOpenAI
# from langchain_core.prompts import ChatPromptTemplate

def main():
    # llm = ChatOpenAI(model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    # chain = prompt | llm
    # result = chain.invoke({"input": "..."})

    out_dir = resolve_output("build/chain")
    metrics = {
        "accuracy": 0.91,
        "cost_usd": float(os.environ.get("AIMAKE_PARAM_TEMPERATURE", "0.05")),
        "tokens": 1200,
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")

if __name__ == "__main__":
    main()
```

**Tips**

- Put the prompt text (or template file) in a separate `prompt` artifact so prompt-only edits rebuild the chain without reindexing.
- Set `cost_estimate` on the artifact so `aimake plan` shows dollars/tokens before you spend.
- Pin `external.revision` when the provider updates models behind the same name. Use `aimake probe` when drift detection is enabled — see [Trust & reproducibility](/docs/trust).
- Hyperparameter trials inject `AIMAKE_PARAM_*` env vars; read them in the chain script as shown above.

---

## LlamaIndex

Build and persist a vector index as a `vector_index` artifact. Document changes invalidate the index; unchanged docs restore from cache.

```yaml
artifacts:
  index:
    type: vector_index
    depends_on: [documents]
    command: python src/build_llamaindex.py
    outputs:
      - build/llama_index/
    external:
      - name: embed-model
        provider: openai
        model: text-embedding-3-small
        revision: "2024-01"
```

```python
# src/build_llamaindex.py
from aimake.utils.outputs import resolve_output

# from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

def main():
    out = resolve_output("build/llama_index")
    # docs = SimpleDirectoryReader("data").load_data()
    # index = VectorStoreIndex.from_documents(docs)
    # index.storage_context.persist(persist_dir=str(out))
    (out / "index.json").write_text('{"status": "built"}', encoding="utf-8")

if __name__ == "__main__":
    main()
```

**Tips**

- Model the raw docs as a `dataset` (or `source:`) artifact so fingerprinting tracks content, not mtime.
- Use `aimake watch` (optionally `--build`) while editing prompts or files under `data/`.
- Downstream RAG eval can depend on `index` + `prompt` and skip when only an unrelated report changed.

---

## Hugging Face Transformers

Two complementary paths:

1. **Hub sync** via the [Hugging Face plugin](/docs/plugins#hugging-face) (`aimake hf pull/push`)
2. **Train / embed / eval scripts** as normal artifacts (GPU optional)

Enable the plugin when you need Hub I/O:

```yaml
plugins:
  huggingface:
    enabled: true

artifacts:
  embedder:
    type: model
    source: models/embedder
    metadata:
      huggingface:
        repo_id: sentence-transformers/all-MiniLM-L6-v2
        pull: true

  finetune:
    type: model
    depends_on: [dataset]
    command: python src/finetune.py
    outputs:
      - models/finetuned/
    resources:
      gpu: 1
```

```bash
pip install aimake[huggingface]
aimake hf pull embedder
aimake build finetune
```

Inside `src/finetune.py`, write checkpoints under `resolve_output("models/finetuned")` so failed runs do not leave half-written weights (atomic outputs). Add `validation` size / non-empty checks on the model directory when you promote to the [registry](/docs/registry).

---

## CI with GitHub Action

Run adapted pipelines in CI with the official action (plan JSON + optional PR comments):

```yaml
- uses: arjun988/aimake/.github/actions/aimake@v2
  with:
    config: aimake.yaml
    extra: s3
```

Or run the [published container](/docs/docker):

```yaml
- run: |
    docker run --rm -v "$PWD:/workspace" -w /workspace \
      ghcr.io/arjun988/aimake:latest build
```

Full CI patterns: [CI/CD](/docs/ci-cd).

---

## Checklist

| Goal | Approach |
|------|----------|
| Skip unchanged LLM calls | Fingerprint prompts + `external` model pins |
| Fail bad evals in CI | `validation` + `aimake eval --check` |
| Iterate locally | `aimake watch` / [Interactive TUI](/docs/tui) |
| Share cache across laptops | [Remote & team cache](/docs/remote-cache) |
| Log to W&B | [W&B plugin](/docs/plugins#weights--biases) |
