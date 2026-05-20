# Reproduction Milestones

**Current: method_runs**

## Progress Log

### [2026-05-20 01:23] - method_runs
- Audited the prior implementation and found root-only landmarks and missing COL internal object bounds.
- Reworked SUL-Tree construction to use graph-aware recursive partitions with local per-node landmarks and SDLs.
- Reworked COL-Tree construction to store object-specific min/max bounds for internal nodes and ODLs for leaves.
- Verified the revised method on a tiny local graph; submitting the first compute job to test the core kFN claim on US48.

## Stop Justification
- Not stopped. A compute job is being submitted to validate whether the revised implementation supports `core_claim`.
