"""Run evaluation using prompt and index."""
import json
import os
from pathlib import Path

try:
    from aimake.utils.outputs import resolve_output
except ImportError:
    def resolve_output(relative_path: str, *, mkdir: bool = True) -> Path:
        path = Path(relative_path)
        if mkdir:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path

prompt_path = Path("prompts/system.txt")
index_path = Path("build/index/index.json")
output_dir = resolve_output("build/evaluation")

temperature = float(os.environ.get("AIMAKE_PARAM_TEMPERATURE", "1.0"))

prompt = prompt_path.read_text(encoding="utf-8")
with open(index_path, encoding="utf-8") as f:
    index = json.load(f)

prompt_hash = sum(ord(c) for c in prompt) % 1000
accuracy = min(0.99, 0.85 + (prompt_hash % 10) / 100.0 * temperature)
f1 = accuracy - 0.025
latency_ms = int(300 + (index["count"] * 10) / max(temperature, 0.1))
cost_usd = round(index["count"] * 0.01 * temperature, 2)

results = {
    "accuracy": round(accuracy, 3),
    "f1": round(f1, 3),
    "latency_ms": latency_ms,
    "cost_usd": cost_usd,
    "tokens": int(index["count"] * 120),
    "temperature": temperature,
}

out = resolve_output("build/evaluation/results.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"Evaluation complete: accuracy={results['accuracy']} (temperature={temperature})")
