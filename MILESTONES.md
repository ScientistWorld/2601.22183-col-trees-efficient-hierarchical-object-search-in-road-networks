# Reproduction Milestones

**Current: method_runs**

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

## Stop Justification
- Not stopped. A compute job is being submitted to validate whether the revised implementation supports `core_claim`.
