# Research Direction

## Research Problem
This paper addresses efficient POI search in road networks using aggregate k-nearest neighbors, k-farthest neighbors, and range queries. The challenge is that exact network distance computation (shortest paths) is expensive on large networks, requiring efficient indexing to prune the search space.

## Direction
Work on exact indexed road-network POI search. Successful submissions should reduce exact-distance verification and candidate retrieval while preserving exact answers for the same AkNN, kFN, and range-query tasks.

## Approach Scope
The scientist may improve:
- Graph partitioning or covering strategies
- Distance-bound tightness and admissible pruning rules
- Candidate ordering and query-control logic
- Memory/compute tradeoffs in index construction
- Handling of multiple POI sets or aggregate functions

## Out of Bounds
- Replacing the indexed-pruning task with a complete distance oracle or full all-pairs table.
- Precomputing all-pairs shortest paths. The goal is an index that enables fast queries, not brute-force.
- Using external geographic databases or map APIs. Must work with the provided graph structure.
