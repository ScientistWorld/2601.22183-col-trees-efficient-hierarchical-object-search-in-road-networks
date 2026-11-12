#!/bin/bash
# Score every method directory under the results root in the paper's own
# setting (original NW travel times, real POI categories as published) and
# write scoring/scores.json.
#
# A method directory must contain submission.json (see briefing/evaluation.md).
#
# Usage: bash scripts/evaluate.sh [results_root] [--output FILE]

set -euo pipefail

cd /home/user

RESULTS_ROOT="/home/user/experiment_results"
if [ $# -gt 0 ] && [[ "$1" != -* ]]; then
    RESULTS_ROOT="$1"
    shift
fi
OUTPUT_FILE="/home/user/scoring/scores.json"
while [ $# -gt 0 ]; do
    case "$1" in
        --output|-o) OUTPUT_FILE="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

mkdir -p /home/user/scoring/details
python3 eval/evaluate.py --root "$RESULTS_ROOT" --output "$OUTPUT_FILE" \
    --details /home/user/scoring/details/paper.json
echo "Scores written to $OUTPUT_FILE"
