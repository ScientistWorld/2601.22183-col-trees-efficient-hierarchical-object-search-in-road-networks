#!/bin/bash
# Full pipeline: build the reference method and baseline submissions, score them
# on the held-out test, train and paper settings, then run the hardening probes
# (variants and shortcuts through the hidden test; see HARDENING.md).
# Resumable: finished score files are kept and their step is skipped.

set -uo pipefail
cd /home/user

python3 -c "import numpy, scipy; print('numpy', numpy.__version__, 'scipy', scipy.__version__)"
nproc; date -u

status=0
step() {  # step <output> <command...>
    local out=$1
    shift
    if [ -s "$out" ]; then
        echo "--- $out exists, skipped"
        return 0
    fi
    echo "=== $(date -u +%H:%M:%S) $* ==="
    time "$@" || { echo "!!! failed: $*" >&2; status=1; }
}

# Only method directories may live directly under experiment_results/.
if [ ! -s experiment_results/colt/sul_range.json ] || [ ! -s experiment_results/colt_default/sul.json ]; then
    time bash scripts/method.sh || exit 1
fi
if [ ! -s experiment_results/alt_filter/alt.json ] || [ ! -s experiment_results/bruteforce/root.json ]; then
    time bash scripts/baseline.sh || exit 1
fi

# Evaluator speed-up check: the reference test scores of job aa2d48d7 were produced
# by the previous Engine (full-network limited searches).  Rescore with the current
# Engine (region-restricted searches) and require identical numbers; otherwise put
# the previous Engine back (hardening/lib/engine_revert.py) and keep its scores.
H=hardening/results
mkdir -p "$H"
if [ ! -s "$H/engine_check.txt" ] && [ -s scoring/scores_test.json ] && [ ! -s "$H/scores_test_old_engine.json" ]; then
    cp scoring/details/test.json "$H/details_test_old_engine.json" 2>/dev/null
    mv scoring/scores_test.json "$H/scores_test_old_engine.json"
fi

# Reference scores (the baseline every later attempt is ranked against).
step scoring/scores_test.json bash scripts/evaluate_test.sh

if [ ! -s "$H/engine_check.txt" ] && [ -s "$H/scores_test_old_engine.json" ] && [ -s scoring/scores_test.json ]; then
    if python3 - "$H/scores_test_old_engine.json" scoring/scores_test.json > "$H/engine_check.tmp" <<'PY'
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:3])
bad = [(e, m, k, a[e]["results"][m][k], b.get(e, {}).get("results", {}).get(m, {}).get(k))
       for e in a for m in a[e]["results"] for k in a[e]["results"][m]
       if a[e]["results"][m][k] != b.get(e, {}).get("results", {}).get(m, {}).get(k)]
same_methods = all(set(a[e]["results"]) == set(b.get(e, {}).get("results", {})) for e in a)
print("identical" if not bad and same_methods else "DIFFERENT " + json.dumps(bad[:20]))
sys.exit(0 if not bad and same_methods else 1)
PY
    then
        echo "engine check: identical scores with the region-restricted Engine"
    else
        echo "!!! engine check failed: reverting to the previous Engine" >&2
        python3 hardening/lib/engine_revert.py eval/test/evaluate.py eval/train/evaluate.py
        cp "$H/scores_test_old_engine.json" scoring/scores_test.json
        cp "$H/details_test_old_engine.json" scoring/details/test.json 2>/dev/null
    fi
    cat "$H/engine_check.tmp"
    mv "$H/engine_check.tmp" "$H/engine_check.txt"
fi

# Variants and shortcuts through the hidden test (+ the secret-reading probe unisolated).
echo "=== $(date -u +%H:%M:%S) hardening probes: test ==="
bash hardening/run_probes.sh test || status=1
step scoring/scores_train.json bash scripts/evaluate_train.sh
step scoring/scores.json bash scripts/evaluate.sh
bash hardening/run_probes.sh summary || status=1
# Improved variants on the public split (train/test agreement of honest variants).
echo "=== $(date -u +%H:%M:%S) hardening probes: train ==="
bash hardening/run_probes.sh train || status=1
bash hardening/run_probes.sh summary || status=1

for f in scores scores_train scores_test; do
    echo "=== scoring/$f.json ==="
    cat "scoring/$f.json" 2>/dev/null || echo "(missing)"
done

python3 validate.py --compare --post-design || status=1
date -u
exit $status
