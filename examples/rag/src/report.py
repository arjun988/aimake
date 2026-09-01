"""Generate evaluation report."""
import json
from datetime import datetime, timezone
from pathlib import Path

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
