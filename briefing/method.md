# Method: COL-Tree and SUL-Tree for Hierarchical POI Search

## Overview

The proposed approach introduces two hierarchical index structures to accelerate POI search in road networks:

1. **SUL-Tree (Subgraph-Landmark Tree)**: Partitions the road network hierarchically and precomputes landmark-based distance lower and upper bounds for efficient network traversal.
2. **COL-Tree (Compacted Object-Landmark Tree)**: A compact version of the SUL-Tree specialized for a given POI set, with POI-specific distance information at leaf nodes.

The key idea is to use precomputed landmark distances to derive lower and upper bounds on network distances, enabling aggressive pruning during query answering.

## SUL-Tree Construction

### Hierarchical Partitioning

The road network is recursively partitioned into b-way trees (default b = 8). Each node in the tree corresponds to a subgraph of the original network.

- **Internal nodes**: Represent a partition of their parent's subgraph, containing a subset of the vertices and edges.
- **Leaf nodes**: Represent small, atomic subgraphs (clusters of vertices).
- Each node is assigned a set of **m landmark vertices** (default m = 2-4, depending on query type).

### Subgraph Distance List (SDL)

For each internal node with subgraph G_s and landmark set L_s, the SUL-Tree precomputes and stores for every vertex v in G_s:
  SDL(v, L_s) = { d(v, l) | l ∈ L_s }

This is the distance from v to each landmark in the node's landmark set. These precomputed values serve as the basis for lower and upper bound estimates during query processing.

### Landmark Selection Strategies

Two landmark selection strategies are used:
- **Random landmarks**: For AkNN queries, landmarks are selected uniformly at random from the subgraph. This provides good average-case bounds.
- **Slice landmarks**: For kFN queries, a structured selection is used (e.g., selecting vertices at specific quantiles of the distance distribution). This provides tighter bounds for farthest-neighbor queries.

## COL-Tree Construction

The COL-Tree is built on top of the SUL-Tree structure but is specialized for the POI set P.

### Leaf Node Structure

Leaf nodes of the COL-Tree store at most λ POIs (default λ = 256). Each leaf node maintains:
- A sorted list of its contained POIs
- For each POI p in the leaf, an **Object Distance List (ODL)**: { d(p, l) | l ∈ L_leaf } sorted by distance to landmarks

The ODL enables efficient candidate pruning based on landmark distances.

### Upper and Lower Bounds via Landmarks

Given a query vertex q and a POI p, the precomputed landmark distances provide bounds:

- **Lower bound**: Using triangle inequality with landmarks: d(q, p) ≥ |d(q, l) - d(p, l)| for any landmark l
- **Upper bound**: d(q, p) ≤ d(q, l) + d(p, l)

The maximum over all lower bounds provides the best (tightest) lower bound estimate. These bounds are used to prune the search space.

### Convexity Preservation

For aggregate functions (sum, max), the landmark-based bounds preserve the convexity of the distance function. This property ensures that the bounds are effective for pruning even in multi-POI queries (AkNN). Specifically, the lower bound on agg(d(q_i, p)) can be derived from landmark distances, allowing branch-and-bound search over the tree.

## Query Processing

### AkNN Query Algorithm

Given query set Q, aggregate function agg, and k:
1. Start from the root of the COL-Tree.
2. For each node, compute landmark-based lower and upper bounds on the aggregate distance to any POI in the node's subtree.
3. If the lower bound is already worse than the current best answer, prune the entire subtree.
4. Recursively descend into promising child nodes.
5. At leaf nodes, examine individual POIs using their ODLs, computing actual distances only when necessary to verify candidates.
6. Maintain a priority structure of the current best k candidates, updating bounds as candidates are found.

The search is a best-first or depth-first branch-and-bound over the tree, guided by the landmark-based bounds.

### kFN Query Algorithm

Given query vertex q and k:
1. Traverse the COL-Tree similarly, but use bounds tailored to maximizing the minimum distance.
2. The slice landmark selection strategy provides tighter bounds for farthest-neighbor queries.
3. Prune subtrees where even the upper bound is worse than the current best minimum distance.
4. At leaf nodes, use ODLs to quickly identify promising candidates without computing all distances.

### Range Query Algorithm

Given query vertex q and radius r:
1. Traverse the COL-Tree, using landmark bounds to determine if any POI in a subtree can be within distance r.
2. Prune subtrees where the lower bound exceeds r.
3. At leaf nodes, check individual POIs using their ODLs.

## Parameters

Key parameters affecting performance and memory:
- **b** (branching factor): Default 8. Higher b increases fanout but may weaken bounds.
- **λ** (leaf capacity): Default 256. Maximum POIs per leaf node.
- **m** (landmark count): 2 for AkNN, 4 for kFN. More landmarks give tighter bounds but increase memory.
- Landmark selection strategy: Random vs. slice, chosen per query type.

## Key Claims

1. Landmark-based bounds are tight enough to prune the vast majority of the network during query processing.
2. The convexity-preserving property of the bounds enables effective pruning even for aggregate queries.
3. The COL-Tree's compact POI-specific index reduces memory overhead compared to a full network index.
4. The hierarchical structure enables early pruning of large portions of the search space.
5. Different landmark selection strategies optimize for different query types (nearest vs. farthest).
