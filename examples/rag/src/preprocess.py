"""Preprocess raw dataset into normalized JSONL."""
import json
from pathlib import Path

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
        f.write(json.dumps(rec) + "\n")

print(f"Processed {len(processed)} records -> {out}")
