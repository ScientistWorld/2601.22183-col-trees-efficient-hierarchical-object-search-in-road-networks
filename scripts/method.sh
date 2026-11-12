#!/bin/bash
# Build the paper's method submissions (COL-Tree query algorithms over a
# SUL-Tree index) into experiment_results/<method>/:
#
#   colt          per-query SUL-Tree parameters finalised in the paper
#                 (Table 8; alpha=1024, 16 ALT root landmarks, lambda=256):
#                   kFN   b=4 m=4 Slice-Based Furthest Border
#                   AkNN  b=8 m=2 Random
#                   range b=8 m=2 Border Minmax
#   colt_default  one SUL-Tree for every query type with the paper's default
#                 parameters (Section 9.5: b=8, m=2, alpha=1024, Random)
#
# Each directory gets a submission.json naming the solver command and the
# structure used for each task; the evaluators do the rest.
# Data must already be present (scripts/download.sh, run on a node with internet).

set -euo pipefail

cd /home/user

OUT="${EXPERIMENT_RESULTS:-/home/user/experiment_results}"

build() {  # build <out> <b> <m> <policy>
    python3 method/build.py --out "$1" --b "$2" --m "$3" --policy "$4" \
        --alpha 1024 --root-landmarks 16 --seed 1
}

echo "=== colt (paper Table 8 parameters per query type) ==="
mkdir -p "$OUT/colt"
build "$OUT/colt/sul_kfn.json"   4 4 slice
build "$OUT/colt/sul_aknn.json"  8 2 random
build "$OUT/colt/sul_range.json" 8 2 minmax
cat > "$OUT/colt/submission.json" <<'EOF'
{"command": ["python3", "method/solver.py", "--lam", "256", "--bounds", "paper"],
 "structures": {"kfn": "sul_kfn.json", "aknn": "sul_aknn.json", "range": "sul_range.json"}}
EOF

echo "=== colt_default (b=8, m=2, Random for every query type) ==="
mkdir -p "$OUT/colt_default"
build "$OUT/colt_default/sul.json" 8 2 random
cat > "$OUT/colt_default/submission.json" <<'EOF'
{"command": ["python3", "method/solver.py", "--lam", "256", "--bounds", "paper"],
 "structures": {"kfn": "sul.json", "aknn": "sul.json", "range": "sul.json"}}
EOF

echo "=== method submissions ready ==="
ls -l "$OUT/colt" "$OUT/colt_default"
