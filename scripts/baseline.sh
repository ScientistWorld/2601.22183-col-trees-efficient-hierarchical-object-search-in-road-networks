#!/bin/bash
# Build the baseline submissions into experiment_results/<method>/:
#
#   alt_filter  reveals every object, bounds each one with 16 random ALT
#               landmarks and verifies candidates in bound order (the paper's
#               AUB-PHL competitor for kFN, the landmark multi-step filter
#               for AkNN / range).
#   bruteforce  reveals every object and computes every exact distance.
#
# Both use a single root node holding every vertex (no hierarchy).

set -euo pipefail

cd /home/user

OUT="${EXPERIMENT_RESULTS:-/home/user/experiment_results}"

echo "=== alt_filter (16 ALT landmarks) ==="
mkdir -p "$OUT/alt_filter"
python3 baseline/build.py --out "$OUT/alt_filter/alt.json" --landmarks 16 --seed 1
cat > "$OUT/alt_filter/submission.json" <<'EOF'
{"command": ["python3", "baseline/solver.py", "--mode", "alt_filter"],
 "structures": {"kfn": "alt.json", "aknn": "alt.json", "range": "alt.json"}}
EOF

echo "=== bruteforce ==="
mkdir -p "$OUT/bruteforce"
python3 baseline/build.py --out "$OUT/bruteforce/root.json" --landmarks 1 --seed 1
cat > "$OUT/bruteforce/submission.json" <<'EOF'
{"command": ["python3", "baseline/solver.py", "--mode", "bruteforce"],
 "structures": {"kfn": "root.json", "aknn": "root.json", "range": "root.json"}}
EOF

echo "=== baseline submissions ready ==="
