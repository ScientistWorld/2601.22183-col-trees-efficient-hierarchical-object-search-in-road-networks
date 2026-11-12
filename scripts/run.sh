#!/bin/bash
# Full pipeline: build method + baseline submissions, then score them with the
# main (paper setting), train and held-out test evaluators.

set -uo pipefail

cd /home/user

python3 -c "import numpy, scipy; print('numpy', numpy.__version__, 'scipy', scipy.__version__)"

# Only method directories may live directly under experiment_results/.
set -e
time bash scripts/method.sh
time bash scripts/baseline.sh
set +e

status=0
for step in evaluate evaluate_train evaluate_test; do
    echo "=== $step ==="
    if ! time bash "scripts/$step.sh"; then
        echo "!!! $step failed" >&2
        status=1
    fi
done

for f in scores scores_train scores_test; do
    echo "=== scoring/$f.json ==="
    cat "scoring/$f.json" 2>/dev/null || echo "(missing)"
done

python3 validate.py --compare --post-design || status=1
exit $status
