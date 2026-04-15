#!/bin/bash
# Evaluate the public train slice from pre-generated method result artifacts.
# Usage: ./scripts/evaluate_train.sh <results_json_or_dir> [method_name]

set -e

cd /home/user

mkdir -p scoring

RESULTS_FILE="${1:-}"
METHOD_NAME="${2:-colt_phl}"
OUTPUT_FILE="/home/user/scoring/scores_train.json"

if [ -z "$RESULTS_FILE" ]; then
    RESULTS_FILE="/home/user/experiment_results"
fi

if [ ! -e "$RESULTS_FILE" ]; then
    echo "Error: Results path not found: $RESULTS_FILE"
    echo "Usage: ./scripts/evaluate_train.sh <results_json_or_dir> [method_name]"
    exit 1
fi

python3 /home/user/eval/train/evaluate.py "$RESULTS_FILE" \
    --method-name "$METHOD_NAME" \
    --output "$OUTPUT_FILE"

echo "Train-slice evaluation complete. Scores written to $OUTPUT_FILE"
