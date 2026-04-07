# Research Direction

## Research Problem
This paper addresses efficient POI search in road networks using aggregate k-nearest neighbors, k-farthest neighbors, and range queries. The challenge is that exact network distance computation (shortest paths) is expensive on large networks, requiring efficient indexing to prune the search space.

## Core Contribution
The paper introduces hierarchical landmark-based indexes (SUL-Tree and COL-Tree) that precompute landmark distances to derive lower and upper bounds on network distances, enabling aggressive pruning during query processing. The scientist must improve this kind of contribution: landmark-based hierarchical indexing for road network POI search.

## Approach Scope
The scientist may improve:
- Landmark selection strategies (better coverage, tighter bounds)
- Tree partitioning algorithms (how the graph is divided into subtrees)
- Bound computation formulas (tighter lower/upper bounds)
- Query processing algorithms (better pruning strategies, PQ ordering)
- Memory/compute tradeoffs in index construction
- Aggregate function handling (sum vs. max vs. other aggregations)

## Out of Bounds
- Replacing the landmark-based index with Hub Labels, Contraction Hierarchies, or other distance oracle approaches. The paper's contribution is specifically the COL-Tree/SUL-Tree landmark-based approach.
- Precomputing all-pairs shortest paths. The goal is an index that enables fast queries, not brute-force.
- Using external geographic databases or map APIs. Must work with the provided graph structure.

