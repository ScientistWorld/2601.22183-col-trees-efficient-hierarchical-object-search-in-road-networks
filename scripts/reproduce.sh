#!/bin/bash
# Reproduce the paper's results end-to-end.
#
# This script runs inside the compute container and should call
# scripts/baseline.sh and scripts/method.sh to run baselines and
# the paper's method, each of which calls scripts/evaluate.sh.
#
# Assumes:
#   - Container is built (environment/container.sif)
#   - Data and models are downloaded (via scripts/download.sh)
#   - Working directory is /home/user
#
# This is the "gold standard" reproduction —
# You do not need to run this, but keep this in good shape
# so other agents can easily run a full loop of reproduction and get the paper's numbers.

set -e

cd /home/user

echo "=== Running AkNN experiments ==="
python3 method/experiment.py --network usroads-48 --query aknn --n-queries 50 --density 0.001 --agg max --Q-size 4 --k 10 --seed 42 -o experiment_results/aknn_results.json

echo "=== Running kFN experiments ==="
python3 method/experiment.py --network usroads-48 --query kfn --n-queries 50 --density 0.001 --k 10 --seed 42 -o experiment_results/kfn_results.json

echo "=== Running Range experiments ==="
python3 method/experiment.py --network usroads-48 --query range --n-queries 50 --density 0.001 --radius-pct 1.0 --seed 42 -o experiment_results/range_results.json

echo "=== Evaluating results ==="
python3 eval/evaluate.py experiment_results/aknn_results.json --method-name colt_phl -o scoring/scores.json

echo "=== Reproduction complete ==="
echo "Results in experiment_results/"
echo "Scores in scoring/scores.json"
