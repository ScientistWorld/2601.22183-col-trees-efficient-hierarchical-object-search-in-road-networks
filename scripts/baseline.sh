#!/bin/bash
# Build the baseline submissions into experiment_results/<method>/:
#
#   alt_filter  reveals every object, bounds each one with 16 random ALT
#               landmarks and verifies candidates in bound order (the paper's
#               AUB-PHL competitor for kFN, the landmark multi-step filter
#               for AkNN / range).  As in the paper, it uses the same ALT index
#               (the same random draw) as the COL-Tree reference for each query
#               type (method/tuned_root.json, written by scripts/method.sh).
#   bruteforce  reveals every object and computes every exact distance.
#
# Both use a single root node holding every vertex (no hierarchy).

set -euo pipefail

cd /home/user

OUT="${EXPERIMENT_RESULTS:-/home/user/experiment_results}"

echo "=== alt_filter (16 ALT landmarks, the reference's draw per query type) ==="
mkdir -p "$OUT/alt_filter"
rm -f "$OUT/alt_filter/alt.json"
read -r SK SA SR <<<"$(python3 -c "import json; c = json.load(open('method/tuned_root.json'))['chosen']; print(c['kfn'], c['aknn'], c['range'])")"
for S in $(printf '%s\n' "$SK" "$SA" "$SR" | sort -u); do
    python3 baseline/build.py --out "$OUT/alt_filter/alt_seed$S.json" --landmarks 16 --seed "$S"
done
cat > "$OUT/alt_filter/submission.json" <<EOF
{"command": ["python3", "baseline/solver.py", "--mode", "alt_filter"],
 "structures": {"kfn": "alt_seed$SK.json", "aknn": "alt_seed$SA.json", "range": "alt_seed$SR.json"}}
EOF

echo "=== bruteforce ==="
mkdir -p "$OUT/bruteforce"
python3 baseline/build.py --out "$OUT/bruteforce/root.json" --landmarks 1 --seed 1
cat > "$OUT/bruteforce/submission.json" <<'EOF'
{"command": ["python3", "baseline/solver.py", "--mode", "bruteforce"],
 "structures": {"kfn": "root.json", "aknn": "root.json", "range": "root.json"}}
EOF

echo "=== baseline submissions ready ==="
