# Framework adapters

Wrap existing LangChain, LlamaIndex, or Hugging Face pipelines as aimake artifacts.

---

## LangChain

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

Pin `external.revision` when the provider updates models behind the same name.

---

## LlamaIndex

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
from pathlib import Path
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

Use `aimake watch` while editing prompts or documents under `data/`.

---

## Hugging Face Transformers

Enable the built-in plugin:

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
```

```yaml
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

---

## CI with GitHub Action

```yaml
- uses: arjun988/aimake/.github/actions/aimake@v1
  with:
    config: aimake.yaml
    extra: s3
```

See [`.github/actions/aimake/action.yml`](../.github/actions/aimake/action.yml).
