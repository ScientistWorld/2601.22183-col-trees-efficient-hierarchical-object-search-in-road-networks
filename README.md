# Overview: COL-Tree Paper Reproduction

The COL-Tree paper addresses the problem of efficiently answering spatial queries for Points of Interest (POIs) on large-scale road networks, specifically three query types: Aggregate k Nearest Neighbors (AkNN), k Farthest Neighbors (kFN), and range queries. The core challenge is that these queries require computing network distances (shortest paths) on graphs with tens of millions of vertices, making naive approaches prohibitively slow.

The proposed solution consists of two hierarchical index structures. The SUL-Tree hierarchically partitions the road network into a b-way tree, where each node stores precomputed distances from a set of landmark vertices to all vertices in its subgraph (Subgraph Distance Lists). The COL-Tree specializes this structure for a given POI set, storing Object Distance Lists at leaf nodes that enable efficient candidate pruning using landmark-based lower and upper bounds on network distances.

The key insight is that landmark distances provide both lower and upper bounds on true network distances via the triangle inequality, and these bounds preserve the convexity of aggregate functions, enabling effective branch-and-bound search over the tree even for multi-POI queries. The approach achieves reported speedups of up to 100x for AkNN, 10,000x for kFN, and 2.7x for range queries compared to baseline methods like IER-PHL and NVD-PHL, while requiring only seconds of preprocessing and megabytes of index storage.

This reproduction targets the DIMACS US road network (23.9M vertices, 57.7M edges) with multiple POI types, evaluating query time, number of shortest-path computations, and candidate counts as the primary performance metrics, with correctness verification against brute-force results on sampled subgraphs.

---

# Problem Definition: Hierarchical POI Search in Road Networks

## Domain

A road network is modeled as a weighted undirected graph G = (V, E), where V is the set of vertices (intersections and endpoints) and E is the set of edges (road segments), each with a positive travel cost (e.g., distance or travel time). A set of Points of Interest (POIs) P is a subset of vertices: P ⊆ V. Example POI types include schools, parks, hospitals, and gas stations.

Network distance d(u, v) between two vertices is defined as the length of the shortest path between them in G. This distance is computed via shortest-path algorithms (e.g., Dijkstra's algorithm) and can be expensive on large networks.

## Query Types

### 1. Aggregate k Nearest Neighbors (AkNN)

Given:
- A set of query vertices Q ⊆ V
- An integer k ≥ 1
- An aggregate function agg ∈ {sum, max}

Return a set S ⊆ P of k POIs that minimizes:
  agg( d(q, p) for q ∈ Q )

over all subsets S of size k from P.

Informally: find the k POIs that are collectively closest to the query set Q according to the given aggregate.

For `sum`, the objective is to minimize the total distance from all query vertices to the k POIs. For `max`, the objective is to minimize the maximum distance from any query vertex to its farthest POI in the set.

### 2. k Farthest Neighbors (kFN)

Given:
- A single query vertex q ∈ V
- An integer k ≥ 1

Return a set S ⊆ P of k POIs that maximizes:
  min_{p ∈ S} d(q, p)

Informally: find the k POIs that are farthest from q, i.e., maximize the coverage radius such that the closest POI in the result set is as far from q as possible.

### 3. Range Queries

Given:
- A query vertex q ∈ V
- A radius r ≥ 0

Return the set { p ∈ P | d(q, p) ≤ r }.

All POIs within network distance r from q.

## Challenges

- **Scale**: Real-world road networks can have tens of millions of vertices and edges (e.g., the DIMACS network with ~24M vertices, ~58M edges), making repeated shortest-path computations costly.
- **Multi-objective nature**: AkNN involves finding a set of k POIs jointly, not independently, which is combinatorially harder than finding a single nearest neighbor.
- **Query diversity**: Different query types (AkNN, kFN, Range) require different algorithmic strategies.
- **Dynamic POI sets**: The POI set P may change between queries (different POI types), requiring the index to support multiple object sets efficiently.

## Scope

This reproduction targets the three query types above on static road networks with static POI sets, evaluated on the DIMACS US road network with various POI types (schools, parks, hospitals, etc.).

---

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

---

# Evaluation Plan: COL-Tree Reproduction

## Dataset

- **Road network**: DIMACS US road network (~23.9 million vertices, ~57.7 million edges)
- **POI sets**: Multiple POI types including schools, parks, hospitals, and gas stations
- **Query sets**: Query vertices sampled from the road network according to the protocols described below

## Performance Metrics

### Primary Metrics

1. **Average Query Time (ms)**
   - Wall-clock time per query, averaged over all queries in the test set
   - Lower is better
   - Target: match or improve upon the reported COL-Tree query times in the paper

2. **Number of Network Distance Computations**
   - Count of actual shortest-path computations (Dijkstra/BI-Dijkstra runs) performed during query answering
   - This is a key indicator of index efficiency and pruning power
   - Lower is better
   - Target: significantly fewer distance computations than baseline methods

3. **Number of Candidate Objects Retrieved**
   - Count of POIs examined or returned as candidates during query processing
   - Lower is better (indicates tighter pruning)

### Secondary Metrics

4. **Index Construction Time**
   - Time to build the spatial index (preprocessing)
   - Reported for both tree structures

5. **Index Storage Size (MB/GB)**
   - Memory or disk footprint of the preprocessed index structures
   - Lower is better

6. **Recall / Result Correctness**
   - For each query, verify that returned results match the exact optimum (verified by brute force on a manageable subgraph)
   - Must be 100% for all queries

## Evaluation Protocol

### Query Generation

- **AkNN queries**: Generate query sets Q of size |Q| ∈ {1, 2, 4, 8, 16} and k ∈ {1, 5, 10}. Sample query vertices uniformly at random from the road network.
- **kFN queries**: Single-vertex queries (|Q| = 1) with k ∈ {1, 5, 10}.
- **Range queries**: Single-vertex queries with radius r sampled from a distribution covering small, medium, and large ranges.

### Query Sets

- Use at least 500 queries per configuration (query type, k, |Q|, radius).
- Split into a development set (for parameter tuning) and a test set (for final evaluation).
- Queries should be spatially diverse.

### Baseline Methods

Evaluate the following baseline methods alongside the proposed method:

1. **IER-PHL**: Incremental Euclidean Restriction with Pruned Highway Labeling. Uses Euclidean distance as a heuristic to guide network expansion.
2. **NVD-PHL**: Network Voronoi Diagram approach with concurrent expansion.
3. **AUB-PHL**: Brute-force baseline using ALT (A*, Landmarks, Triangle inequality) upper bounds for pruning.
4. **COLT-PHL**: The proposed method (COL-Tree-based approach).

### Experimental Design

1. **Preprocessing**: Build all index structures (SUL-Tree, COL-Tree, and baselines' indexes) once before measuring query times.
2. **Query answering**: For each query, measure query time, distance computation count, and candidate count. Run each query multiple times to reduce timing noise.
3. **Memory measurement**: Measure index size after full preprocessing.

### Expected Targets

Based on the paper's reported results, the following performance targets are expected:

| Query Type | Metric | Baseline (IER-PHL/NVD-PHL) | Expected with COL-Tree |
|---|---|---|---|
| AkNN | Query time | ~100-1000 ms | ~1-10 ms (up to 100× speedup) |
| AkNN | Distance computations | High | Significantly reduced |
| kFN | Query time | ~10000× baseline | ~1-10 ms |
| kFN | Distance computations | Very high | Drastically reduced |
| Range | Query time | Moderate | 2-7× speedup |
| Range | Distance computations | Moderate | Reduced |

### Correctness Verification

- Before evaluating performance, run a small set of queries with known ground truth (computed by brute force on a sampled subgraph) to verify that the implementation returns correct results.
- All methods must achieve 100% recall (no false negatives).

---

# Reproduction Log

### Iteration 1: MiniMax-M2.7
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 5m | **GPU**: 0.0h

<details>
<summary>Progress Log</summary>

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

</details>

### Iteration 2: glm-5.1
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 10m | **GPU**: 0.0h

<details>
<summary>Progress Log</summary>

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

</details>

### Iteration 3: gpt-5.4
- **Milestone**: `core_claim` | **Status**: done
- **GPU**: 0.0h


---

# Reproduction Milestones

**Current: core_claim**

## Progress Log

## Stop Justification
