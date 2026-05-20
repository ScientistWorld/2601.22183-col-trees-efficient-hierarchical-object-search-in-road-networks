# Verification Report

## Initial Assessment

The previous workflow had reached `secondary_claims`, but the current workspace had already been reset to `method_runs` after a deeper audit. That reset is justified. The code and evaluator have been tightened, but the checked-in `experiment_results/core_claim` artifacts are stale: they do not contain the per-query outputs now required for independent correctness recomputation.

## Issues Found

- **Critical**: `scripts/evaluate.sh /home/user/experiment_results/core_claim` fails because the saved artifacts lack `queries.per_query`. Current `scores.json`, `scores_train.json`, and `scores_test.json` are structurally valid but stale relative to the stricter evaluator.
- **Minor**: High-level public scoring documents still named implementation structures directly in places where future from-scratch agents should only see constraints and direction.
- **Minor**: Ignored Python bytecode directories were present under source/data directories.

## Fixes Applied

- Verified both URLs in `scripts/download.sh` with `curl -I -L --max-time 15`; both returned HTTP 200.
- Confirmed committed code does not reference `/shared` paths and `eval/` does not import from `method/`.
- Tightened `briefing/evaluation.md`, `scoring/TARGETS.md`, `scoring/CONSTRAINTS.md`, and `scoring/DIRECTION.md` to keep public gym guidance focused on the task, constraints, and allowed research direction rather than implementation names.
- Confirmed `scripts/run.sh` is prepared to regenerate method artifacts, run main/train/test evaluation, and validate scores in a CPU test job.

## Final Judgment

The workspace is not ready for final `done` yet because the saved artifacts and score files are stale under the current evaluator. The appropriate next action is a CPU test job to regenerate `experiment_results/core_claim`, `scoring/scores.json`, `scoring/scores_train.json`, and `scoring/scores_test.json`. If that job passes, the prior `secondary_claims` milestone can be restored; until then the honest milestone is `method_runs`.

- Milestone: method_runs
- Ready for gym use: partial
- Confidence: medium
- Key limitation: fresh post-audit benchmark artifacts are pending regeneration; the benchmark also uses an accessible US48/synthetic-POI replacement rather than the paper's original full-scale data and distance-oracle setup.
