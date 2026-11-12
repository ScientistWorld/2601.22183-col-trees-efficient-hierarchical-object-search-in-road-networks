# Scientist Constraints

## Preprocessing Structure
The scientist must build and use a reusable road-network index for pruning query work. Precomputing all-pairs distances, storing a full distance matrix, or relying on a complete distance oracle is not allowed; those approaches replace the benchmark challenge with exhaustive preprocessing.

## Dataset
The scientist must use the provided road network (US48 with 126K vertices or Pennsylvania with 1M+ vertices). No external road networks or additional geographic data. POI sets must be subsets of graph vertices.

## Allowed Approach Family
Methods should stay within exact road-network POI indexing and pruning. Improvements may change partitioning, bound tightness, candidate ordering, memory layout, or object-set handling, but they must still answer the same graph-distance queries exactly and report the same candidate/lookup metrics.

## Correctness
All query results must match exact ground truth. A scientist who improves query time by sacrificing accuracy should score WORSE.

## Compliance Checklist
- [ ] Uses a reusable graph/POI index for pruning
- [ ] No precomputed all-pairs distance matrix or full distance oracle
- [ ] Results are 100% correct (verified against brute force)
- [ ] Uses the provided road network dataset (no external networks)
