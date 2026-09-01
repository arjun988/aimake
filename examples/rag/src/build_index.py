"""Build a simple vector index from embeddings."""
import json
from pathlib import Path

embeddings_path = Path("build/embeddings/embeddings.json")
output_dir = Path("build/index")
output_dir.mkdir(parents=True, exist_ok=True)

with open(embeddings_path, encoding="utf-8") as f:
    embeddings = json.load(f)

index = {
    "dimension": 8,
    "count": len(embeddings),
    "ids": [e["id"] for e in embeddings],
}
out = output_dir / "index.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(index, f, indent=2)

print(f"Built index with {len(embeddings)} vectors -> {out}")
