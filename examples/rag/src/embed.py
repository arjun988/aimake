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
        vec = [
            int(hashlib.sha256(f"{text}:{i}".encode()).hexdigest()[:2], 16) / 255.0
            for i in range(8)
        ]
        embeddings.append({"id": rec["id"], "vector": vec})

out = output_dir / "embeddings.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(embeddings, f, indent=2)

print(f"Generated {len(embeddings)} embeddings -> {out}")
