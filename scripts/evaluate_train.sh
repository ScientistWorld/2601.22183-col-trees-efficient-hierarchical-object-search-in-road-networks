#!/bin/bash
# Evaluate the public train slice from pre-generated method result artifacts.
# Usage: ./scripts/evaluate_train.sh [results_json_or_dir]

set -euo pipefail

cd /home/user

mkdir -p scoring

RESULTS_PATH="${1:-/home/user/experiment_results}"
OUTPUT_FILE="/home/user/scoring/scores_train.json"

if [ ! -e "$RESULTS_PATH" ]; then
    echo "Error: results path not found: $RESULTS_PATH"
    echo "Usage: ./scripts/evaluate_train.sh [results_json_or_dir]"
    exit 1
fi

python3 - "$RESULTS_PATH" "$OUTPUT_FILE" "/home/user/eval/train/evaluate.py" <<'PYEOF'
import json
import subprocess
import sys
import tempfile
from pathlib import Path

results_path = Path(sys.argv[1])
output_file = Path(sys.argv[2])
eval_script = Path(sys.argv[3])


def discover_method_inputs(path: Path) -> list[tuple[str, Path]]:
    if path.is_file():
        return [("colt_phl", path)]

    method_dirs = [
        candidate for candidate in sorted(path.iterdir())
        if candidate.is_dir() and any(candidate.glob("*.json"))
    ]
    if method_dirs:
        return [(candidate.name, candidate) for candidate in method_dirs]

    if any(path.glob("*.json")):
        return [("colt_phl", path)]

    raise SystemExit(f"No JSON result artifacts found under {path}")


def merge_scores(dst: dict, src: dict) -> None:
    for experiment_name, experiment_payload in src.items():
        dst.setdefault(experiment_name, {"results": {}})
        dst[experiment_name]["results"].update(experiment_payload.get("results", {}))


discovered = discover_method_inputs(results_path)
print("Found methods:", " ".join(name for name, _ in discovered))

merged_scores: dict = {}
with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir_path = Path(tmpdir)
    for method_name, method_path in discovered:
        tmp_output = tmpdir_path / f"{method_name}.json"
        subprocess.run(
            [
                "python3",
                str(eval_script),
                str(method_path),
                "--method-name",
                method_name,
                "--output",
                str(tmp_output),
            ],
            check=True,
        )
        with tmp_output.open("r") as handle:
            merge_scores(merged_scores, json.load(handle))

output_file.parent.mkdir(parents=True, exist_ok=True)
with output_file.open("w") as handle:
    json.dump(merged_scores, handle, indent=2)
    handle.write("\n")

print(f"Train-slice evaluation complete. Scores written to {output_file}")
PYEOF
