# Evaluation Targets

## Primary: kFN Pruning Efficiency

Measure how much of the POI set must be retrieved and verified while answering exact k farthest-neighbor queries.

- **Metric**: `candidates_ratio` (lower is better)
- **Metric**: `lookup_reduction_vs_brute` (higher is better)

## Constraint: Correctness

Returned query results must be exact. Ties at the kth boundary may be returned in any order or subset.

- **Metric**: `accuracy` (1.0 = all evaluated queries exact)

## Constraint: Preprocessing

The method must build a reusable graph/POI preprocessing structure rather than answering every query from scratch with all-pairs distances.

- **Metric**: `sul_time_s` and `col_time_s` (lower is better, reported as overhead)
