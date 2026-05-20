#!/bin/bash
# End-to-end reproduction entry point for the current core claim.
# Assumes data has already been fetched by scripts/download.sh.

set -euo pipefail

cd /home/user

bash scripts/method.sh
bash scripts/evaluate_train.sh /home/user/experiment_results/core_claim
bash scripts/evaluate_test.sh /home/user/experiment_results/core_claim

echo "=== Reproduction complete ==="
echo "Results in experiment_results/core_claim/"
echo "Scores in scoring/scores.json"
