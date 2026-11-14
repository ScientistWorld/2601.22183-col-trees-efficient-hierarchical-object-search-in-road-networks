#!/bin/bash
# Full pipeline (one CPU job):
#   1. reference submissions: structures, the lambda parameter test on the train
#      split (scripts/method.sh -> scripts/tune_lambda.sh), baselines; the probe
#      structures are built meanwhile (hardening/build.sh structures);
#   2. scoring runs, in parallel where the node allows, in priority order:
#      held-out test (scoring/scores_test.json), the hardening probe groups
#      (hardening/run_probes.sh), the public split (scoring/scores_train.json),
#      the paper's own setting (scoring/scores.json), the seed reruns;
#   3. hardening/summarize.py and validate.py.
# Resumable: finished outputs are kept and their step is skipped; an interrupted
# evaluator run resumes after its last finished task (--checkpoint).

set -uo pipefail
cd /home/user

python3 -c "import numpy, scipy; print('numpy', numpy.__version__, 'scipy', scipy.__version__)"
date -u
L=hardening/results/joblogs
mkdir -p "$L" scoring/details

# Parallel slots: usable CPUs (affinity and cgroup quota) and memory (~3 GB per evaluator).
P=$(python3 - <<'PY'
import os, sys
cpus = len(os.sched_getaffinity(0))
quota = None
try:
    a, b = open("/sys/fs/cgroup/cpu.max").read().split()
    quota = None if a == "max" else int(a) / int(b)
except Exception:
    try:
        a = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read())
        b = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read())
        quota = a / b if a > 0 else None
    except Exception:
        pass
mem = None
for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
    try:
        v = open(path).read().strip()
        if v != "max" and int(v) < 1 << 50:
            mem = int(v) / 2 ** 30
            break
    except Exception:
        pass
host = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30
eff = min(cpus, quota) if quota else cpus
slots = max(1, min(int(eff), int((mem or host) // 3), 6))
print(f"cpus={cpus} quota={quota} cgroup_mem_gb={mem} host_mem_gb={host:.0f} -> slots={slots}", file=sys.stderr)
print(slots)
PY
)
echo "parallel slots: $P"

status=0

# 1. Submissions.
bash hardening/build.sh structures > "$L/probe_structures.log" 2>&1 &
pid_structures=$!
time bash scripts/method.sh || { echo "!!! scripts/method.sh failed" >&2; exit 1; }
time bash scripts/baseline.sh || { echo "!!! scripts/baseline.sh failed" >&2; exit 1; }
wait "$pid_structures" || { echo "!!! probe structures failed" >&2; status=1; }
tail -3 "$L/probe_structures.log"
bash hardening/build.sh > "$L/probe_submissions.log" 2>&1 || { echo "!!! probe submissions failed" >&2; status=1; }
tail -4 "$L/probe_submissions.log"

# 2. Scoring runs.
step() {  # step <name> <output> <command...>: run unless the output exists
    local name=$1 out=$2
    shift 2
    if [ -s "$out" ]; then
        echo "--- $name: $out exists, skipped"
        return 0
    fi
    echo "=== $(date -u +%H:%M:%S) start $name ==="
    local t0=$SECONDS rc=0
    "$@" > "$L/$name.log" 2>&1 || rc=$?
    echo "=== $(date -u +%H:%M:%S) end $name (rc=$rc, $(( (SECONDS - t0) / 60 )) min) ==="
    tail -4 "$L/$name.log"
    return $rc
}
launch() {  # run a step in the background once a slot is free
    while [ "$(jobs -rp | wc -l)" -ge "$P" ]; do
        wait -n || true
    done
    step "$@" &
}
eval_full() {  # eval_full <evaluator args...> <output> <details> <checkpoint>
    local n=$#
    local out=${@:n-2:1} det=${@:n-1:1} ck=${@:n:1}
    python3 "${@:1:n-3}" --output "$out.tmp" --details "$det" --checkpoint "$ck" \
        && mv "$out.tmp" "$out" && rm -f "$ck"
}

launch ref_test scoring/scores_test.json eval_full eval/test/evaluate.py --root experiment_results \
    scoring/scores_test.json scoring/details/test.json scoring/details/ckpt_test.json
for g in colt_a colt_b alt; do
    launch "probes_$g" "hardening/results/parts/test_$g.json" bash hardening/run_probes.sh test "$g"
done
launch ref_train scoring/scores_train.json eval_full eval/train/evaluate.py --setting train --root experiment_results \
    scoring/scores_train.json scoring/details/train.json scoring/details/ckpt_train.json
launch paper scoring/scores.json eval_full eval/evaluate.py --root experiment_results \
    scoring/scores.json scoring/details/paper.json scoring/details/ckpt_paper.json
launch probes_seeds hardening/results/parts/test_seeds.json bash hardening/run_probes.sh test seeds
wait

for f in scoring/scores_test.json scoring/scores_train.json scoring/scores.json \
         hardening/results/parts/test_{colt_a,colt_b,alt,seeds}.json; do
    [ -s "$f" ] || { echo "!!! missing $f" >&2; status=1; }
done

# 3. Summary and checks.
bash hardening/run_probes.sh summary || status=1
for f in scores scores_train scores_test; do
    echo "=== scoring/$f.json ==="
    cat "scoring/$f.json" 2>/dev/null || echo "(missing)"
done
cat hardening/results/summary.md 2>/dev/null
python3 validate.py || status=1
python3 validate.py --compare --post-design | tail -40
date -u
exit $status
