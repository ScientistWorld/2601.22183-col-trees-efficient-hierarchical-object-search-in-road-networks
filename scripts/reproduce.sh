#!/bin/bash
# End-to-end reproduction entry point.
# Assumes data has already been fetched by scripts/download.sh (needs internet).

set -euo pipefail

cd /home/user

bash scripts/method.sh
bash scripts/baseline.sh
bash scripts/evaluate.sh
bash scripts/evaluate_train.sh
bash scripts/evaluate_test.sh

echo "=== Reproduction complete ==="
echo "Submissions in experiment_results/<method>/"
echo "Scores in scoring/scores.json, scoring/scores_train.json, scoring/scores_test.json"
