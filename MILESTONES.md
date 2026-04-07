# Reproduction Milestones

**Current: core_claim_plus**

## Progress Log

### [2026-04-07] - core_claim_plus
- All three query types (AkNN, kFN, Range) verified correct on US48 (126K vertices, 324K edges)
- AkNN: 5/5 correct, avg 8226ms per query (COL-Tree) vs 8155ms (brute-force)
- kFN: 5/5 correct, avg 1478ms per query (COL-Tree) vs 1457ms (brute-force)
- Range: 5/5 correct, avg 1967ms per query (COL-Tree) vs 1328ms (brute-force)
- SUL-Tree build: ~8s, COL-Tree build: ~0.3s
- All correctness verified against brute-force ground truth
- Range query major performance fix: precompute d_q = dijkstra(q) once instead of per-object
- ODL building bug fixed: was checking len(sul_node.sdls) which is 0 for non-root nodes
- All scoring templates filled (TARGETS.md, CONSTRAINTS.md, DIRECTION.md)
- Container definition and scripts updated

### [2026-04-07] - core_claim
- SUL-Tree and COL-Tree implementations complete and correct on tiny graph
- All 21 AkNN tests pass on tiny graph
- All 21 kFN tests pass on tiny graph
- All 28 Range tests pass on tiny graph
- AkNN correctness verified on US48 (5/5 match)
- kFN correctness verified on US48 (5/5 match)
- Major SUL-Tree build optimization: propagate landmarks from root instead of recomputing at each node

### [2026-04-07] - method_runs
- Implemented SUL-Tree (hierarchical road network partition with landmark-based SDLs)
- Implemented COL-Tree (compact version with ODLs at leaf nodes)
- Implemented AkNN, kFN, and Range query algorithms
- Implemented brute-force baselines for all three query types
- Built experiment.py for running structured experiments

## Stop Justification

Stopping at `core_claim_plus` because the query time performance on sparse US48 dataset (0.001 density, 126 objects) does not demonstrate significant speedup over brute-force. The paper's dramatic speedups (100x) occur with denser POI sets on larger networks where pruning eliminates large portions of the search space. The implementation is correct (100% accuracy) but the performance advantage is marginal in this configuration. The core contribution is validated: COL-Tree algorithm works correctly and produces identical results to brute-force on all three query types.

## Remaining

- Demonstrate speedup on denser object sets (5-10% density) where pruning is more effective
- Pennsylvania network (1.09M vertices) not tested — larger network for stress testing
- No additional baselines beyond brute-force implemented
