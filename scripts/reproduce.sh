#!/bin/bash
# Reproduce the paper's results end-to-end.
# Runs AkNN, kFN, and range queries on US48 road network, then evaluates.

set -e

cd /home/user

mkdir -p experiment_results

echo "=== Running kFN experiments ==="
python3 method/experiment.py --network usroads-48 --query kfn --n-queries 50 --density 0.001 --k 10 --seed 42 -o experiment_results/kfn_results.json

echo "=== Running AkNN experiments ==="
python3 method/experiment.py --network usroads-48 --query aknn --n-queries 50 --density 0.001 --agg max --Q-size 4 --k 10 --seed 42 -o experiment_results/aknn_results.json

echo "=== Running Range experiments ==="
python3 method/experiment.py --network usroads-48 --query range --n-queries 50 --density 0.001 --radius-pct 1.0 --seed 42 -o experiment_results/range_results.json

echo "=== Evaluating all results ==="
bash scripts/evaluate.sh /home/user/experiment_results

echo "=== Reproduction complete ==="
echo "Results in experiment_results/"
echo "Scores in scoring/scores.json"
