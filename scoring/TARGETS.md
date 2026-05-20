# Evaluation Targets

## Primary: kFN Pruning Efficiency

Measure how much of the POI set must be retrieved and verified while answering exact k farthest-neighbor queries.

- **Metric**: `candidates_ratio` (lower is better)
- **Metric**: `lookup_reduction_vs_brute` (higher is better)

## Constraint: Correctness

Returned query results must be exact. Ties at the kth boundary may be returned in any order or subset.

- **Metric**: `accuracy` (1.0 = all evaluated queries exact)

## Constraint: Preprocessing

The index must be built from hierarchical subgraph landmarks and a compact object index rather than all-pairs distances.

- **Metric**: `sul_time_s` and `col_time_s` (lower is better, reported as overhead)

