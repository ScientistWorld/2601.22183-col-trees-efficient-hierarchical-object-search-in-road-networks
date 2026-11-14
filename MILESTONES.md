# Reproduction Milestones

**Current: secondary_claims**

## Progress Log

### [2026-05-20 01:23] - method_runs
- Audited the prior implementation and found root-only landmarks and missing COL internal object bounds.
- Reworked SUL-Tree construction to use graph-aware recursive partitions with local per-node landmarks and SDLs.
- Reworked COL-Tree construction to store object-specific min/max bounds for internal nodes and ODLs for leaves.
- Verified the revised method on a tiny local graph; submitting the first compute job to test the core kFN claim on US48.

### [2026-05-20 01:27] - method_runs
- Continued the audit and found that no fresh `experiment_results/core_claim` artifacts existed for the revised implementation.
- Fixed kFN leaf processing so a revisited COL leaf retrieves additional ODL objects instead of being requeued without progress.
- Resubmitting the US48 kFN core job to generate real scores before restoring `core_claim`.

### [2026-05-20 01:29] - method_runs
- Container build failed because `environment/container.def` tried to bake gitignored `data/downloads/*` files into the image.
- Removed the fragile `%files` section; runtime uses the bind-mounted workspace and `scripts/download.sh` repopulates `data/downloads/` from tracked data or verified URLs.
- Resubmitting the same CPU core job after the environment packaging fix.

### [2026-05-20 01:32] - core_claim
- CPU job `90b0e53b-aab` completed the US48 kFN core experiment with 12/12 exact queries.
- Reproduced the core benefit/constraint pair: exact kFN correctness with `candidates_ratio=0.1650` and `lookup_reduction_vs_brute=6.0601`.
- Expanding the same core experiment to a second object density before attempting a higher milestone.

### [2026-05-20 01:36] - core_claim_plus
- CPU job `e203f389-121` completed kFN at object densities 0.05 and 0.10 with 24/24 exact queries.
- Averaged score improved to `candidates_ratio=0.1566` and `lookup_reduction_vs_brute=6.4020` while preserving `accuracy=1.0`.
- Adding small AkNN and range runs to test secondary query claims next.

### [2026-05-20 01:40] - core_claim_plus
- CPU job `26aa2eab-2d1` verified AkNN and range correctness, but range scanned all objects (`candidates_ratio=1.0`).
- Fixed range leaf processing to use the ODL landmark-distance window implied by triangle inequality before exact checks.
- Resubmitting secondary query coverage before claiming `secondary_claims`.

### [2026-05-20 01:44] - secondary_claims
- CPU job `d266aebb-8f5` reran kFN, AkNN, and range after range ODL pruning.
- All evaluated query families were exact: kFN, AkNN, and range each reached `accuracy=1.0`.
- Secondary pruning now holds: AkNN `candidates_ratio=0.1666`, range `candidates_ratio=0.0844`, and kFN `lookup_reduction_vs_brute=6.4020`.

### [2026-05-20 02:21] - secondary_claims
- Refreshed the evaluator to populate p90 and worst-query candidate-ratio constraint metrics from saved per-query method artifacts.
- Re-ran `scripts/evaluate.sh`, `scripts/evaluate_train.sh`, `scripts/evaluate_test.sh`, and `python validate.py --compare`; all checks pass.

### [2026-05-20 02:23] - secondary_claims
- Final verification passed after cleaning method-agnostic documentation, documenting replacement benchmark reference rows, and moving brute-force baseline helpers under `baseline/`.
- Verified download URLs and reran `python validate.py --compare`; all checks pass.

### [2026-05-20 02:27] - secondary_claims
- Re-audited the submitted workspace, moved the AUB-PHL-style helper used by the experiment harness into `baseline/`, and removed the stale baseline module from `method/`.
- Re-ran bytecode checks, `scripts/evaluate.sh`, and `python3 validate.py --compare`; all checks pass.

### [2026-05-20 02:32] - method_runs
- Sub-agent audit found that the previous results relied on stale artifacts and exact full-graph local-landmark distances, so the honest current milestone is reset pending a fresh job.
- Removed full-graph local-landmark SDL caching, switched COL node bounds to root-landmark lower/upper-bound substitution, changed kFN leaves to enqueue object candidates by upper bound before exact verification, and made result artifacts include per-query outputs.
- Updated evaluation to recompute main accuracy from method outputs and exact ground truth, tightened train/test evaluators to require per-query correctness and exact lookup counts, and changed `scripts/run.sh` to regenerate method artifacts before scoring.
- Bytecode checks and a tiny local graph smoke test pass; submitting a CPU job to regenerate the benchmark artifacts.

### [2026-05-20 02:35] - method_runs
- Final verification found that the checked-in `experiment_results/core_claim` artifacts are still stale and fail standalone `scripts/evaluate.sh` because they lack `queries.per_query`.
- Verified both download URLs with `curl -I -L --max-time 15`; both returned HTTP 200.
- Cleaned public scoring guidance to avoid exposing implementation names in method-agnostic/high-level gym documents.
- Keeping the milestone at `method_runs` and submitting the prepared CPU job to regenerate artifacts and scores before any final `secondary_claims` sign-off.

### [2026-05-20 02:39] - secondary_claims
- CPU job `714f3f12-b67` regenerated post-audit artifacts and completed `scripts/run.sh` with exit code 0.
- Fresh artifacts now include `queries.per_query`, per-query correctness flags, and kFN exact-lookup counts required by the stricter evaluator.
- `python3 validate.py --compare` passed in the job; regenerated scores show exact kFN, AkNN, and range results with nontrivial candidate pruning.

### [2026-11-14 12:30] - secondary_claims
- Hardening iteration 12 (`HARDENING.md`): the reference's lambda is now tuned per query type on the train split, as the paper tunes its parameters (kFN 16, AkNN 32, range 32). Re-tuning lambda no longer pays (-0.014 / -0.045 rank).
- Workloads cover the paper's density range (uniform d = 0.001, 0.01, 0.1). The hidden test averages over three hidden travel-time conditions.
- The paper's effects now appear beyond noise on the hidden test. The local-landmark ablation scores -0.284 rank. Against the ALT filter, COL-Tree computes fewer exact distances at d = 0.01 (+0.14 +- 0.04) and d = 0.1 (+0.35 +- 0.07), and retrieves 1-3 orders of magnitude fewer candidates.
- Honest improvements beat the reference and transfer to train (colt_best +0.061 test / +0.041 train). The shared-backbone seed spread is 0.007. Re-drawing root landmarks moves test kFN by up to +0.069 without a train signal; this is documented as an unfixed weakness.

## Stop Justification
- Completed at milestone `secondary_claims`.
