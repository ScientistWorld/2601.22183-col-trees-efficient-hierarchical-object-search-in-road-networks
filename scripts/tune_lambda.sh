#!/bin/bash
# Parameter testing for the COL-Tree leaf size lambda on the public (train)
# split, as the paper does on its own network (Section 9.6, Table 8):
#
#   1. method/tuning/lam<L>/ submissions: the reference structures with the
#      default random draw (method/tuning_root/seed1/sul_*.json, built by
#      scripts/method.sh) with --lam L for every L of the grid;
#   2. eval/train/evaluate.py scores them, one process per query type
#      (method/tuning/sweep_<task>.json, details_<task>.json);
#   3. method/tune_lambda.py picks lambda per query type and writes
#      method/tuned_lambda.json (scripts/tune_root.sh then picks the random root
#      draw and writes experiment_results/colt/).
#
# Needs the default-draw structures from scripts/method.sh.  Resumable: finished sweep files
# are kept; an interrupted evaluator run resumes after its last finished task.

set -uo pipefail
cd /home/user

T=method/tuning
GRID="${LAMBDA_GRID:-8 16 32 64 128 256 512}"
mkdir -p "$T"
for L in $GRID; do
    mkdir -p "$T/lam$L"
    cat > "$T/lam$L/submission.json" <<EOF
{"command": ["python3", "method/solver.py", "--lam", "$L", "--bounds", "paper"],
 "structures": {"kfn": "../../tuning_root/seed1/sul_kfn.json",
                "aknn": "../../tuning_root/seed1/sul_aknn.json",
                "range": "../../tuning_root/seed1/sul_range.json"}}
EOF
done

status=0
pids=()
for task in kfn aknn range; do
    if [ -s "$T/sweep_$task.json" ]; then
        echo "--- $T/sweep_$task.json exists, skipped"
        continue
    fi
    echo "=== $(date -u +%H:%M:%S) lambda sweep ($task) on the train split ==="
    python3 eval/train/evaluate.py --setting train --root "$T" --tasks "$task" \
        --output "$T/sweep_$task.json.tmp" --details "$T/details_$task.json" \
        --checkpoint "$T/ckpt_$task.json" > "$T/log_$task.txt" 2>&1 &
    pids+=($!)
done
for p in "${pids[@]}"; do
    wait "$p" || status=1
done
for task in kfn aknn range; do
    if [ -s "$T/sweep_$task.json.tmp" ]; then
        mv "$T/sweep_$task.json.tmp" "$T/sweep_$task.json"
        rm -f "$T/ckpt_$task.json"
    fi
    tail -3 "$T/log_$task.txt" 2>/dev/null
done
[ $status -eq 0 ] || { echo "!!! lambda sweep failed" >&2; exit 1; }
python3 method/tune_lambda.py
