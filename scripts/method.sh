#!/bin/bash
# Build the paper's method submissions (COL-Tree query algorithms over a
# SUL-Tree index) into experiment_results/<method>/:
#
#   colt          per-query SUL-Tree parameters finalised in the paper
#                 (Table 8; alpha=1024, 16 random ALT root landmarks):
#                   kFN   b=4 m=4 Slice-Based Furthest Border
#                   AkNN  b=8 m=2 Random
#                   range b=8 m=2 Border Minmax
#                 with two index parameters set by parameter testing on this
#                 network's public (train) split, as the paper sets its own on its
#                 network (Section 9.6), one parameter at a time:
#                   1. the COL-Tree leaf size lambda per query type, on the default
#                      random draw (seed 1): scripts/tune_lambda.sh ->
#                      method/tuned_lambda.json
#                   2. the random ALT root-landmark draw per query type, best of six
#                      random draws at that lambda: scripts/tune_root.sh ->
#                      method/tuned_root.json, experiment_results/colt/
#   colt_default  the paper's untuned defaults for every query type
#                 (Section 9.5: b=8, m=2, alpha=1024, Random, lambda=256, default draw)
#
# Each directory gets a submission.json naming the solver command and the
# structure used for each task; the evaluators do the rest.
# Data must already be present (scripts/download.sh, run on a node with internet).
# Set RETUNE=1 to redo both parameter tests even when their outputs exist.

set -euo pipefail

cd /home/user

OUT=/home/user/experiment_results

build() {  # build <out> <b> <m> <policy>
    [ -s "$1" ] && [ "${REBUILD:-0}" != 1 ] && { echo "--- $1 exists"; return 0; }
    python3 method/build.py --out "$1" --b "$2" --m "$3" --policy "$4" \
        --alpha 1024 --root-landmarks 16 --seed 1
}

echo "=== colt structures, default random draw (paper Table 8 parameters per query type) ==="
D=/home/user/method/tuning_root/seed1
mkdir -p "$D" "$OUT/colt"
build "$D/sul_kfn.json"   4 4 slice
build "$D/sul_aknn.json"  8 2 random
build "$D/sul_range.json" 8 2 minmax

echo "=== colt_default (b=8, m=2, Random, lambda=256 for every query type) ==="
mkdir -p "$OUT/colt_default"
build "$OUT/colt_default/sul.json" 8 2 random
cat > "$OUT/colt_default/submission.json" <<'EOF'
{"command": ["python3", "method/solver.py", "--lam", "256", "--bounds", "paper"],
 "structures": {"kfn": "sul.json", "aknn": "sul.json", "range": "sul.json"}}
EOF

if [ "${RETUNE:-0}" = 1 ]; then
    rm -f method/tuned_lambda.json method/tuning/sweep_*.json method/tuning_root/sweep_*.json
fi

echo "=== colt: lambda per query type (parameter testing on the train split) ==="
if [ -s method/tuned_lambda.json ]; then
    echo "using method/tuned_lambda.json: --lam $(python3 -c "import json; print(json.load(open('method/tuned_lambda.json'))['lam_spec'])")"
else
    bash scripts/tune_lambda.sh
fi

echo "=== colt: random ALT root-landmark draw per query type (parameter testing on the train split) ==="
bash scripts/tune_root.sh

echo "=== method submissions ready ==="
cat "$OUT/colt/submission.json" "$OUT/colt_default/submission.json"
