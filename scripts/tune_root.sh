#!/bin/bash
# Parameter testing for the random ALT root-landmark draw on the public (train)
# split (method/tune_root.py explains why):
#
#   1. method/tuning_root/seed<S>/: the paper's Table 8 structures (as in
#      scripts/method.sh) built with random draw S, for S in DRAWS (default 1..6;
#      seed 1 is the default draw on which lambda was tested);
#   2. eval/train/evaluate.py scores them at the tuned lambda, one process per
#      query type (method/tuning_root/sweep_<task>.json, details_<task>.json);
#   3. method/tune_root.py keeps the best draw per query type, copies it to
#      experiment_results/colt/ and writes method/tuned_root.json.
#
# Needs method/tuned_lambda.json (scripts/tune_lambda.sh).  Resumable: built
# structures and finished sweep files are kept.

set -uo pipefail
cd /home/user

T=method/tuning_root
DRAWS="${DRAWS:-1 2 3 4 5 6}"
LAM=$(python3 -c "import json; print(json.load(open('method/tuned_lambda.json'))['lam_spec'])") || exit 1

bld() {  # bld <out> <b> <m> <policy> <seed>
    [ -s "$1" ] || python3 method/build.py --out "$1" --b "$2" --m "$3" --policy "$4" \
        --alpha 1024 --root-landmarks 16 --seed "$5"
}
for S in $DRAWS; do
    mkdir -p "$T/seed$S"
    bld "$T/seed$S/sul_kfn.json"   4 4 slice  "$S" || exit 1
    bld "$T/seed$S/sul_aknn.json"  8 2 random "$S" || exit 1
    bld "$T/seed$S/sul_range.json" 8 2 minmax "$S" || exit 1
    cat > "$T/seed$S/submission.json" <<EOF
{"command": ["python3", "method/solver.py", "--lam", "$LAM", "--bounds", "paper"],
 "structures": {"kfn": "sul_kfn.json", "aknn": "sul_aknn.json", "range": "sul_range.json"}}
EOF
done

status=0
pids=()
for task in kfn aknn range; do
    if [ -s "$T/sweep_$task.json" ]; then
        echo "--- $T/sweep_$task.json exists, skipped"
        continue
    fi
    echo "=== $(date -u +%H:%M:%S) root-landmark draw test ($task) on the train split ==="
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
done
[ $status -eq 0 ] || { echo "!!! root-landmark draw test failed" >&2; exit 1; }
python3 method/tune_root.py
