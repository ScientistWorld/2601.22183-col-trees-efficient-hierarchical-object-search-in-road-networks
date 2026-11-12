# Gym scoring audit

Run `bash redteam/run_all.sh` on a CPU job. Each subfolder's `run.sh`
installs that method's code/artifacts, runs the public train command, and
runs **`bash scripts/evaluate_test.sh` with no arguments** in a fresh shell.
The evaluator, Python environment, and process are untouched. Each run saves
its raw artifact, train/test scores, command logs and exit status locally.
Installation is temporary and the original method, baseline, artifacts and
scoring files are restored after every run, including on exceptions.

`reference_seed42` must run first. The brute-force run must precede the cached
answers shortcut. Other artifact-only shortcuts reuse newly generated reference
outputs, which an improve-mode scientist can produce, rather than shipped
hidden results. `original/` is a restoration snapshot; hidden reference metadata
is read only by `summarize.py`, after test execution, for ranking analysis.

`shortcut_faster_bfs` is an honest exact alternative that the scored metrics
cannot distinguish from the reference: its shortest-path implementation is
faster on the unit-weight shipped graph and falls back on weighted graphs.
All other `shortcut_*` directories test departures from the scientific task or
missing validation. The malformed/null and empty cases are negative controls.

The future population used for rank normalization is not available during an
audit. `summary.json` therefore reports raw metrics and two explicitly defined
populations: a pairwise reference/attempt population, and a fixed honest-method
cohort used to compare scientific variants and seed spread. The absolute value
of each coefficient, better direction, experiment weights and missing-value
skipping are implemented exactly as described in the audit request.
