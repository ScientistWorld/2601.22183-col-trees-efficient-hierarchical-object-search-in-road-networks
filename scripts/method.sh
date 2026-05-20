#!/bin/bash
# Run a minimal paper-aligned core-claim experiment for COL-Tree.
#
# This focuses on kFN, where the paper reports the clearest advantage over
# competing heuristics. We test multiple object densities on US48 using the
# paper's tuned kFN parameters where available. Landmark type falls back to
# random because this workspace lacks geometric coordinates for slice-style
# landmark placement.

set -euo pipefail

cd /home/user

bash scripts/download.sh

OUT_DIR="/home/user/experiment_results/core_claim"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json

COMMON_ARGS=(
    --network usroads-48
    --query kfn
    --k 10
    --n-queries 12
    --b 4
    --lam 2048
    --m 4
    --landmark-policy random
    --seed 42
)

echo "=== Running core-claim kFN experiments ==="
for density in 0.05 0.10; do
    python3 method/experiment.py \
        "${COMMON_ARGS[@]}" \
        --density "$density" \
        --output "$OUT_DIR/kfn_density_${density}.json"
done

python3 scripts/summarize_core_claim.py \
    "$OUT_DIR"/kfn_density_*.json \
    --output "$OUT_DIR/summary.json"

bash scripts/evaluate.sh "$OUT_DIR"
