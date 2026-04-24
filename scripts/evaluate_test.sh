#!/bin/bash
# Evaluate the held-out test slice from pre-generated method result artifacts.
# Auto-discovers all method entries from existing score files or results.
# Usage: ./scripts/evaluate_test.sh [results_json_or_dir]

set -e

cd /home/user

mkdir -p scoring

RESULTS_PATH="${1:-/home/user/experiment_results}"
OUTPUT_FILE="/home/user/scoring/scores_test.json"

if [ ! -e "$RESULTS_PATH" ]; then
    echo "Error: Results path not found: $RESULTS_PATH"
    echo "Usage: ./scripts/evaluate_test.sh [results_json_or_dir]"
    exit 1
fi

# Discover all method names from existing scores or results
ALL_METHODS=$(python3 - <<'PYEOF'
import json
import sys
from pathlib import Path

# Try to read from existing scores_train.json if it exists
methods = set()
scores_train = Path("/home/user/scoring/scores_train.json")
if scores_train.exists():
    try:
        data = json.load(open(scores_train))
        for exp in data.values():
            if isinstance(exp, dict) and "results" in exp:
                methods.update(exp["results"].keys())
    except:
        pass

# Also check experiment results files for any methods
results_dir = Path("/home/user/experiment_results")
for f in results_dir.glob("*.json"):
    try:
        data = json.load(open(f))
        # Method name often embedded in results structure
        if "method" in data:
            methods.add(data["method"])
    except:
        pass

# Default to colt_phl if nothing found
if not methods:
    methods.add("colt_phl")

print(" ".join(sorted(methods)))
PYEOF
)

if [ -z "$ALL_METHODS" ]; then
    ALL_METHODS="colt_phl"
fi

echo "Found methods: $ALL_METHODS"

# Score each method
python3 /home/user/eval/test/evaluate.py "$RESULTS_PATH" \
    --method-name "$ALL_METHODS" \
    --output "$OUTPUT_FILE"

echo "Test-slice evaluation complete. Scores written to $OUTPUT_FILE"
