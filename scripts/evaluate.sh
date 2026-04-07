#!/bin/bash
# Evaluation script — the standard way to evaluate work in this environment.
#
# This script must be SELF-CONTAINED using only code in eval/.
# Do NOT import from method/ — evaluate.sh must work even when the
# paper's method code is hidden from a scientist agent.
#
# Design it so that anyone following the same output format can run
# this script to evaluate their results.
#
# OUTPUT CONTRACT: This script MUST write scoring/scores.json containing
# a JSON dict nested by experiment, e.g.:
#   {"aknn_queries": {"results": {"colt_phl": {"avg_query_time_ms": 0.5, "speedup_over_brute": 10.0}}}}
# Experiment and metric names must match the keys in scoring/reference.json.
# This file is read by the system for automated comparison.
#
# Called from run.sh after training, or independently.
# Usage: ./evaluate.sh <results_json> [--method-name NAME] [--output FILE]

set -e

cd /home/user

mkdir -p scoring

# Default arguments
RESULTS_FILE="${1:-}"
METHOD_NAME="${2:-colt_our}"
OUTPUT_FILE="/home/user/scoring/scores.json"

# If results file not provided as arg, look for experiment results
if [ -z "$RESULTS_FILE" ]; then
    # Look for the most recent results
    RESULTS_FILE=$(ls -t /home/user/experiment_results/*.json 2>/dev/null | head -1 || echo "")
fi

if [ -z "$RESULTS_FILE" ] || [ ! -f "$RESULTS_FILE" ]; then
    echo "Error: Results file not found: $RESULTS_FILE"
    echo "Usage: ./evaluate.sh <results_json> [--method-name NAME]"
    exit 1
fi

# Run evaluation
python3 /home/user/eval/evaluate.py "$RESULTS_FILE" \
    --method-name "$METHOD_NAME" \
    --output "$OUTPUT_FILE"

echo "Evaluation complete. Scores written to $OUTPUT_FILE"
