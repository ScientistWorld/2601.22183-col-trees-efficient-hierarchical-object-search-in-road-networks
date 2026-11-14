#!/bin/bash
# Build the paper's method submissions (COL-Tree query algorithms over a
# SUL-Tree index) into experiment_results/<method>/:
#
#   colt          per-query SUL-Tree parameters finalised in the paper
#                 (Table 8; alpha=1024, 16 ALT root landmarks):
#                   kFN   b=4 m=4 Slice-Based Furthest Border
#                   AkNN  b=8 m=2 Random
#                   range b=8 m=2 Border Minmax
#                 and the COL-Tree leaf size lambda chosen per query type by
#                 parameter testing, as the paper does on its own network
#                 (Section 9.6), here on this network's public (train) split:
#                 scripts/tune_lambda.sh -> method/tuned_lambda.json
#   colt_default  the paper's untuned defaults for every query type
#                 (Section 9.5: b=8, m=2, alpha=1024, Random, lambda=256)
#
# Each directory gets a submission.json naming the solver command and the
# structure used for each task; the evaluators do the rest.
# Data must already be present (scripts/download.sh, run on a node with internet).
# Set RETUNE=1 to redo the lambda sweep even when method/tuned_lambda.json exists.

set -euo pipefail

cd /home/user

OUT=/home/user/experiment_results

build() {  # build <out> <b> <m> <policy>
    [ -s "$1" ] && [ "${REBUILD:-0}" != 1 ] && { echo "--- $1 exists"; return 0; }
    python3 method/build.py --out "$1" --b "$2" --m "$3" --policy "$4" \
        --alpha 1024 --root-landmarks 16 --seed 1
}

echo "=== colt structures (paper Table 8 parameters per query type) ==="
mkdir -p "$OUT/colt"
build "$OUT/colt/sul_kfn.json"   4 4 slice
build "$OUT/colt/sul_aknn.json"  8 2 random
build "$OUT/colt/sul_range.json" 8 2 minmax

echo "=== colt_default (b=8, m=2, Random, lambda=256 for every query type) ==="
mkdir -p "$OUT/colt_default"
build "$OUT/colt_default/sul.json" 8 2 random
cat > "$OUT/colt_default/submission.json" <<'EOF'
{"command": ["python3", "method/solver.py", "--lam", "256", "--bounds", "paper"],
 "structures": {"kfn": "sul.json", "aknn": "sul.json", "range": "sul.json"}}
EOF

echo "=== colt: lambda per query type (parameter testing on the train split) ==="
if [ -s method/tuned_lambda.json ] && [ "${RETUNE:-0}" != 1 ]; then
    LAM=$(python3 -c "import json; print(json.load(open('method/tuned_lambda.json'))['lam_spec'])")
    echo "using method/tuned_lambda.json: --lam $LAM"
    cat > "$OUT/colt/submission.json" <<EOF
{"command": ["python3", "method/solver.py", "--lam", "$LAM", "--bounds", "paper"], "structures": {"kfn": "sul_kfn.json", "aknn": "sul_aknn.json", "range": "sul_range.json"}}
EOF
else
    bash scripts/tune_lambda.sh
fi

echo "=== method submissions ready ==="
cat "$OUT/colt/submission.json" "$OUT/colt_default/submission.json"
