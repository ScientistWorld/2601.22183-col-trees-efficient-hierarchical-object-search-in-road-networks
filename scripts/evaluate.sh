#!/bin/bash
# Evaluation script — evaluates experiment results and writes scores.json.
# Metric names match scoring/reference.json experiment keys.
#
# Usage: ./evaluate.sh [results_path] [--method-name NAME] [--output FILE]

set -e

cd /home/user

mkdir -p scoring

RESULTS_PATH="${1:-}"
# This reproduction uses US48 with synthetic POIs and Dijkstra verification,
# not the paper's original DIMACS/OSM+PHL setting. Keep its score row distinct
# from the paper-reported `colt_phl` reference row.
METHOD_NAME="colt_us48_repro"
OUTPUT_FILE="/home/user/scoring/scores.json"

# Parse optional flags
shift 2>/dev/null || true
while [ $# -gt 0 ]; do
    case "$1" in
        --method-name|-m) METHOD_NAME="$2"; shift 2 ;;
        --output|-o) OUTPUT_FILE="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [ -z "$RESULTS_PATH" ]; then
    RESULTS_PATH="/home/user/experiment_results"
fi

python3 /home/user/eval/evaluate.py "$RESULTS_PATH" \
    --method-name "$METHOD_NAME" \
    --output "$OUTPUT_FILE"

echo "Evaluation complete. Scores written to $OUTPUT_FILE"
