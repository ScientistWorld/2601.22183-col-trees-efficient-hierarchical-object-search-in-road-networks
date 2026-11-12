#!/bin/bash
# Score every method directory under the results root on the held-out test
# split (hidden travel-time conditions, hidden object sets and queries) and
# write scoring/scores_test.json.
#
# Usage: bash scripts/evaluate_test.sh [results_root] [--output FILE]

set -euo pipefail

cd /home/user

RESULTS_ROOT="/home/user/experiment_results"
if [ $# -gt 0 ] && [[ "$1" != -* ]]; then
    RESULTS_ROOT="$1"
    shift
fi
OUTPUT_FILE="/home/user/scoring/scores_test.json"
while [ $# -gt 0 ]; do
    case "$1" in
        --output|-o) OUTPUT_FILE="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

mkdir -p /home/user/scoring/details
python3 eval/test/evaluate.py --root "$RESULTS_ROOT" --output "$OUTPUT_FILE" \
    --details /home/user/scoring/details/test.json
echo "Scores written to $OUTPUT_FILE"
