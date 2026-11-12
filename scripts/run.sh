#!/bin/bash
# End-to-end run of the evaluator-owned-distance protocol on the paper's NW
# road network (data/downloads/nw, prepared by scripts/download.sh).
#
#   1. build a SUL-Tree structure (method) and a root-only ALT structure (baseline)
#   2. write submission.json for each into experiment_results/protocol_v2/<name>/
#   3. score both with the held-out test evaluator (eval/test/evaluate.py)
#
# Output goes to experiment_results/protocol_v2/ only; scoring/ is not touched
# until the new pipeline has been verified end to end.

set -euo pipefail

cd /home/user

ROOT=/home/user/experiment_results/protocol_v2
mkdir -p "$ROOT/colt" "$ROOT/alt_filter"

python3 -c "import numpy, scipy; print('numpy', numpy.__version__, 'scipy', scipy.__version__)"

echo "=== build: SUL-Tree (b=8, m=2, alpha=1024, 16 root landmarks) ==="
time python3 method/build.py --out "$ROOT/colt/sul.json" --b 8 --m 2 --alpha 1024 \
    --root-landmarks 16 --policy random --seed 1
cat > "$ROOT/colt/submission.json" <<'EOF'
{"command": ["python3", "method/solver.py", "--lam", "256", "--bounds", "paper"],
 "structures": {"kfn": "sul.json", "aknn": "sul.json", "range": "sul.json"}}
EOF

echo "=== build: root-only ALT structure (16 landmarks) ==="
time python3 baseline/build.py --out "$ROOT/alt_filter/alt.json" --landmarks 16 --seed 1
cat > "$ROOT/alt_filter/submission.json" <<'EOF'
{"command": ["python3", "baseline/solver.py", "--mode", "alt_filter"],
 "structures": {"kfn": "alt.json", "aknn": "alt.json", "range": "alt.json"}}
EOF

echo "=== test evaluator ==="
time python3 eval/test/evaluate.py --root "$ROOT" \
    --output "$ROOT/scores_test.json" --details "$ROOT/details_test.json"

cat "$ROOT/scores_test.json"
