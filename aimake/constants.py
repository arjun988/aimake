"""Project-wide constants."""

from pathlib import Path

AIMAKE_DIR = ".aimake"
CONFIG_FILE = "aimake.yaml"
LOCK_FILE = "aimake.lock"
STATE_DB = "state.db"
CACHE_DIR = "cache"
LOGS_DIR = "logs"
BUILD_DIR = "build"
DEFAULT_JOBS = 0  # 0 means auto-detect CPU count

HASH_PREFIX = "sha256:"
SECRET_REDACTED = "***REDACTED***"

ARTIFACT_TYPES = frozenset({
    "dataset",
    "model",
    "prompt",
    "embedding",
    "embeddings",
    "vector_index",
    "evaluation",
    "report",
    "generic",
})

# Map aliases to canonical type names
ARTIFACT_TYPE_ALIASES = {
    "embeddings": "embedding",
}

INIT_TEMPLATE = """\
project:
  name: {project_name}
  version: "1.0"

# aimake.yaml is executable configuration — commands run on your machine.
# Review this file before running `aimake build`.

artifacts:

  dataset:
    type: dataset
    source: data/train.jsonl

  preprocess:
    type: dataset
    depends_on:
      - dataset
    command: python src/preprocess.py
    outputs:
      - build/processed/

  embeddings:
    type: embedding
    depends_on:
      - preprocess
    command: python src/embed.py
    outputs:
      - build/embeddings/

  index:
    type: vector_index
    depends_on:
      - embeddings
    command: python src/build_index.py
    outputs:
      - build/index/

  prompt:
    type: prompt
    source: prompts/system.txt

  evaluation:
    type: evaluation
    depends_on:
      - index
      - prompt
    command: python src/evaluate.py
    outputs:
      - build/evaluation/
    metrics:
      file: build/evaluation/results.json

  report:
    type: report
    depends_on:
      - evaluation
    command: python src/report.py
    outputs:
      - build/report/
"""

EXAMPLE_PREPROCESS = '''\
"""Preprocess raw dataset into normalized JSONL."""
import json
import sys
from pathlib import Path

input_path = Path("build/.inputs/dataset.jsonl")
if not input_path.exists():
    input_path = Path("data/train.jsonl")
output_dir = Path("build/processed")
output_dir.mkdir(parents=True, exist_ok=True)

records = []
with open(input_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            records.append(json.loads(line))

processed = [{"id": r.get("id", i), "text": r.get("text", "")} for i, r in enumerate(records)]
out = output_dir / "processed.jsonl"
with open(out, "w", encoding="utf-8") as f:
    for rec in processed:
        f.write(json.dumps(rec) + "\\n")

print(f"Processed {len(processed)} records -> {out}")
'''

EXAMPLE_EMBED = '''\
"""Generate deterministic embeddings from processed data."""
import hashlib
import json
from pathlib import Path

processed = Path("build/processed/processed.jsonl")
output_dir = Path("build/embeddings")
output_dir.mkdir(parents=True, exist_ok=True)

embeddings = []
with open(processed, encoding="utf-8") as f:
    for line in f:
        rec = json.loads(line)
        text = rec["text"]
        vec = [int(hashlib.sha256(f"{text}:{i}".encode()).hexdigest()[:2], 16) / 255.0 for i in range(8)]
        embeddings.append({"id": rec["id"], "vector": vec})

out = output_dir / "embeddings.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(embeddings, f, indent=2)

print(f"Generated {len(embeddings)} embeddings -> {out}")
'''

EXAMPLE_BUILD_INDEX = '''\
"""Build a simple vector index from embeddings."""
import json
from pathlib import Path

embeddings_path = Path("build/embeddings/embeddings.json")
output_dir = Path("build/index")
output_dir.mkdir(parents=True, exist_ok=True)

with open(embeddings_path, encoding="utf-8") as f:
    embeddings = json.load(f)

index = {"dimension": 8, "count": len(embeddings), "ids": [e["id"] for e in embeddings]}
out = output_dir / "index.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(index, f, indent=2)

print(f"Built index with {len(embeddings)} vectors -> {out}")
'''

EXAMPLE_EVALUATE = '''\
"""Run evaluation using prompt and index."""
import json
from pathlib import Path

prompt_path = Path("prompts/system.txt")
index_path = Path("build/index/index.json")
output_dir = Path("build/evaluation")
output_dir.mkdir(parents=True, exist_ok=True)

prompt = prompt_path.read_text(encoding="utf-8")
with open(index_path, encoding="utf-8") as f:
    index = json.load(f)

# Deterministic metrics based on prompt content and index size
prompt_hash = sum(ord(c) for c in prompt) % 1000
accuracy = 0.85 + (prompt_hash % 10) / 100.0
f1 = accuracy - 0.025
latency_ms = 300 + (index["count"] * 10)
cost_usd = round(index["count"] * 0.01, 2)

results = {
    "accuracy": round(accuracy, 3),
    "f1": round(f1, 3),
    "latency_ms": latency_ms,
    "cost_usd": cost_usd,
}

out = output_dir / "results.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"Evaluation complete: accuracy={results['accuracy']}")
'''

EXAMPLE_REPORT = '''\
"""Generate evaluation report."""
import json
from pathlib import Path
from datetime import datetime, timezone

eval_path = Path("build/evaluation/results.json")
output_dir = Path("build/report")
output_dir.mkdir(parents=True, exist_ok=True)

with open(eval_path, encoding="utf-8") as f:
    results = json.load(f)

report = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "metrics": results,
    "summary": f"Accuracy: {results['accuracy']:.1%}, F1: {results['f1']:.1%}",
}

out = output_dir / "report.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print(f"Report generated -> {out}")
'''

EXAMPLE_TRAIN_DATA = """\
{"id": "1", "text": "Machine learning enables computers to learn from data."}
{"id": "2", "text": "Natural language processing helps machines understand text."}
{"id": "3", "text": "Retrieval augmented generation combines search with LLMs."}
{"id": "4", "text": "Vector databases store embeddings for similarity search."}
{"id": "5", "text": "Incremental builds save time by skipping unchanged steps."}
"""

EXAMPLE_PROMPT = """\
You are a helpful AI assistant specialized in answering questions about
machine learning and natural language processing. Use the retrieved context
to provide accurate, concise answers. If you are unsure, say so clearly.
"""

def project_root() -> Path:
    """Return the aimake package root (for bundled resources)."""
    return Path(__file__).resolve().parent.parent
