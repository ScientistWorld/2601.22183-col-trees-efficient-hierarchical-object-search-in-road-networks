# Reproduction Milestones

**Current: core_claim_plus**

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

## Stop Justification
- Not stopped. A compute job is being submitted to evaluate secondary AkNN and range query claims.
