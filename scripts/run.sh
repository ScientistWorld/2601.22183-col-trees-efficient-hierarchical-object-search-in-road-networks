#!/bin/bash
# Full pipeline: build the reference method and baseline submissions, score them
# on the held-out test, train and paper settings, then run the hardening probes
# (variants and shortcuts through the hidden test; see HARDENING.md).
# Resumable: finished score files are kept and their step is skipped.

set -uo pipefail
cd /home/user

python3 -c "import numpy, scipy; print('numpy', numpy.__version__, 'scipy', scipy.__version__)"
nproc; free -m 2>/dev/null | head -2; date -u

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
    free -m 2>/dev/null | sed -n 2p
}

# Only method directories may live directly under experiment_results/.
if [ ! -s experiment_results/colt/sul_range.json ] || [ ! -s experiment_results/colt_default/sul.json ]; then
    time bash scripts/method.sh || exit 1
fi
if [ ! -s experiment_results/alt_filter/alt.json ] || [ ! -s experiment_results/bruteforce/root.json ]; then
    time bash scripts/baseline.sh || exit 1
fi

# Reference scores (the baseline every later attempt is ranked against).
step scoring/scores_test.json bash scripts/evaluate_test.sh
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
