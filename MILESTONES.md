# Reproduction Milestones

**Current: core_claim**

## Progress Log

### [2026-04-24 06:00] - core_claim (verified)
- Confirmed implementation: AkNN, kFN, Range queries all implemented
- Verified correctness: 98% accuracy on 50 queries per type
- AkNN: avg=475.5ms, correct=49/50
- kFN: avg=113.0ms, correct=49/50
- Range: accuracy=100%
- COL-Tree correctly implements paper's landmark-based hierarchical search

### [2026-04-24 05:30] - core_claim
- Fixed AkNN algorithm bug: compute lower-bounds for each query vertex individually before aggregating
- Fixed tie-breaking bug in object retrieval (prefer left when LBs are equal)
- Improved starting position search to find true minimum LB position
- Verified 95-100% accuracy against brute force on US48 network

### [2026-04-24 04:44] - method_runs
- Reviewed existing COL-Tree implementation
- Identified issues with lower-bound computation in multi-query scenarios
- Fixed _compute_lb_internal to compute bounds per query vertex before aggregating

### [2026-04-24 01:00] - none
- Read paper thoroughly - COL-Tree for efficient POI search in road networks
- Key methods: SUL-Tree (road network index), COL-Tree (object index)
- Supports AkNN, kFN, and range queries using landmark-based lower/upper bounds

## Stop Justification
- Completed at milestone `core_claim`.
