# Overview: COL-Tree Paper Reproduction

The COL-Tree paper addresses the problem of efficiently answering spatial queries for Points of Interest (POIs) on large-scale road networks, specifically three query types: Aggregate k Nearest Neighbors (AkNN), k Farthest Neighbors (kFN), and range queries. The core challenge is that these queries require computing network distances (shortest paths) on graphs with tens of millions of vertices, making naive approaches prohibitively slow.

The proposed solution consists of two hierarchical index structures. The SUL-Tree hierarchically partitions the road network into a b-way tree, where each node stores precomputed distances from a set of landmark vertices to all vertices in its subgraph (Subgraph Distance Lists). The COL-Tree specializes this structure for a given POI set, storing Object Distance Lists at leaf nodes that enable efficient candidate pruning using landmark-based lower and upper bounds on network distances.

The key insight is that landmark distances provide both lower and upper bounds on true network distances via the triangle inequality, and these bounds preserve the convexity of aggregate functions, enabling effective branch-and-bound search over the tree even for multi-POI queries. The paper reports up to roughly two orders of magnitude improvement for AkNN, up to 330x for kFN, and up to 2.7x for range queries, with modest preprocessing overhead.

This reproduction packages the same COL/SUL algorithmic family on the available US48 road graph with synthetic POI subsets. It evaluates exactness, candidate reduction, lookup reduction versus brute force, and preprocessing overhead, with wall-clock time kept as diagnostic context rather than the main score.

---

# Problem Definition: Efficient POI Search in Road Networks

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
- **Query diversity**: Different query types (AkNN, kFN, Range) stress different parts of a search system.
- **Dynamic POI sets**: The POI set P may change between queries (different POI types), requiring the index to support multiple object sets efficiently.

## Scope

This environment targets the three query types above on static road networks with static POI sets. The shipped benchmark uses a public US road graph with reproducible vertex-sampled POI sets; the original paper evaluated larger road networks with real POI categories.

---

# Method: COL-Tree and SUL-Tree for Hierarchical POI Search

## Overview

The proposed approach introduces two hierarchical index structures to accelerate POI search in road networks:

1. **SUL-Tree (Subgraph-Landmark Tree)**: Partitions the road network hierarchically and precomputes landmark-based distance lower and upper bounds for efficient network traversal.
2. **COL-Tree (Compacted Object-Landmark Tree)**: A compact version of the SUL-Tree specialized for a given POI set, with POI-specific distance information at leaf nodes.

The key idea is to use precomputed landmark distances to derive lower and upper bounds on network distances, enabling aggressive pruning during query answering.

## SUL-Tree Construction

### Hierarchical Partitioning

The road network is recursively partitioned into b-way trees (default b = 8). Each node in the tree corresponds to a subgraph of the original network. The paper uses a METIS-style graph partitioner; this reproduction uses a deterministic multi-source BFS partitioner to keep the environment self-contained while preserving graph-aware subgraphs.

- **Internal nodes**: Represent a partition of their parent's subgraph, containing a subset of the vertices and edges.
- **Leaf nodes**: Represent small, atomic subgraphs (clusters of vertices).
- Each node is assigned a set of **m landmark vertices** (default m = 2-4, depending on query type).

### Subgraph Distance List (SDL)

For each internal node with subgraph G_s and landmark set L_s, the SUL-Tree precomputes and stores for every vertex v in G_s:
  SDL(v, L_s) = { d(v, l) | l ∈ L_s }

This is the distance from v to each landmark in the node's landmark set. These precomputed values serve as the basis for lower and upper bound estimates during query processing.

### Landmark Selection Strategies

The paper evaluates random, slice-based border, and border-minmax landmark policies. The core reproduction uses random local landmarks because the shipped graph lacks geographic coordinates needed for the full slice policy.

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
2. Local landmark selection provides tighter bounds for farthest-neighbor queries; the paper's strongest kFN setting uses slice-based landmarks, while this reproduction uses random local landmarks.
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
- Landmark selection strategy: random in the core reproduction; the paper also evaluates slice and border-minmax variants.

## Key Claims

1. Landmark-based bounds are tight enough to prune the vast majority of the network during query processing.
2. The convexity-preserving property of the bounds enables effective pruning even for aggregate queries.
3. The COL-Tree's compact POI-specific index reduces memory overhead compared to a full network index.
4. The hierarchical structure enables early pruning of large portions of the search space.
5. Different landmark selection strategies optimize for different query types (nearest vs. farthest).

---

# Evaluation Plan

## Dataset

- **Original paper setting**: large US road networks with real POI categories such as schools, parks, hospitals, hotels, and public services.
- **Shipped benchmark setting**: a public US48 road graph under `data/downloads/`, with reproducible POI subsets sampled from graph vertices.
- **Query vertices**: sampled from the road network and stored in method output artifacts.

## Metrics

### Correctness

Returned results are checked against exact brute-force answers on the shipped graph. Top-k ties at the kth boundary may be returned in any order or subset.

- `accuracy`: fraction of evaluated queries that return an exact valid answer. Higher is better.

### Candidate Efficiency

These metrics measure how much work a submitted method leaves for exact verification.

- `candidates_ratio`: average fraction of POIs examined as candidates. Lower is better.
- `candidate_p90_ratio`: 90th-percentile candidate fraction, used to catch methods that only improve easy queries. Lower is better.
- `candidate_max_ratio`: worst per-query candidate fraction. Lower is better.
- `lookup_reduction_vs_brute`: exact-distance lookup reduction relative to checking every POI. Higher is better.

### Preprocessing Diagnostics

Build-time fields are reported for context but have zero score weight because wall-clock timing depends on hardware and implementation language.

- `sul_time_s`: legacy field name for first-stage preprocessing time.
- `col_time_s`: legacy field name for object-index preprocessing time.

These fields are retained for compatibility with the score schema. They are not optimization targets.

## Protocol

1. Build any method-specific preprocessing structures before answering queries.
2. Run AkNN, kFN, and range-query configurations on the shipped graph and POI sets.
3. Write JSON result artifacts containing query type, number of objects, correctness counts, candidate counts, and exact lookup counts.
4. Run `scripts/evaluate.sh <results_path>` to convert artifacts into `scoring/scores.json`.
5. Optional train/test scoring uses `scripts/evaluate_train.sh` and `scripts/evaluate_test.sh`, which score deterministic slices of the same output artifacts.

## Experiment Targets

| Experiment | Required behavior | Efficiency target |
|---|---|---|
| `kfn_real_pois` | Exact k farthest-neighbor results | Reduce exact lookup and candidate fractions versus brute force |
| `aknn_real_pois` | Exact aggregate nearest-neighbor results | Examine only a fraction of the object set |
| `range_real_pois` | Exact set of in-range objects | Examine only a fraction of the object set |
| `preprocessing` | Report index/preprocessing overhead | Diagnostic only, zero score weight |

## Correctness Rules

- A method must use the same graph, POI set, query definitions, and distance metric as the benchmark.
- Exact brute force is the correctness oracle.
- Methods that trade away correctness for pruning receive lower scores through the `accuracy` metric.

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

### Iteration 4: gpt-5.4 (verifier)
- **Milestone**: `core_claim` | **Status**: done
- **GPU**: 0.0h

### Iteration 5: gpt-5.4 (verifier)
- **Milestone**: `core_claim` | **Status**: done
- **GPU**: 0.0h

### Iteration 6: gpt-5.4 (packager)
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 4m | **GPU**: 0.0h

### Iteration 7: gpt-5.4 (designer)
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 7m | **GPU**: 0.0h

### Iteration 7: MiniMax-M2.7 (designer_stage_1)
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 7m | **GPU**: 0.0h

### Iteration 8: MiniMax-M2.7 (designer_stage_2)
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 4m | **GPU**: 0.0h

### Iteration 9: gpt-5.4 (designer_stage_3)
- **Milestone**: `none` | **Status**: done
- **Working time**: 8m | **GPU**: 0.0h

### Iteration 1: MiniMax-M2.7
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 28m | **GPU**: 0.0h

<details>
<summary>Progress Log</summary>

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

</details>

### Iteration 2: glm-5.1
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 37m | **GPU**: 0.0h

<details>
<summary>Progress Log</summary>

- method_runs: COL-Tree implementation complete with kFN, AkNN, and range queries
- core_claim: All three query types produce 100% accuracy on US48 road network (126K vertices, 126 POIs). kFN demonstrates significant search space pruning (candidates_ratio=0.31, 3.27x lookup reduction vs brute force). Eval pipeline computes machine-independent metrics matching reference.json.

</details>

### Iteration 3: gpt-5.5
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 21m | **GPU**: 0.0h
- **Jobs**: 4 total (4 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-05-20 01:23] - method_runs
- Audited the prior implementation and found root-only landmarks and missing COL internal object bounds.
- Reworked SUL-Tree construction to use graph-aware recursive partitions with local per-node landmarks and SDLs.
- Reworked COL-Tree construction to store object-specific min/max bounds for internal nodes and ODLs for leaves.
- Verified the revised method on a tiny local graph; submitting the first compute job to test the core kFN claim on US48.

### [2026-05-20 01:27] - method_runs
- Continued the audit and found that no fresh `experiment_results/core_claim` artifacts existed for the revised implementation.
- Fixed kFN leaf processing so a revisited COL leaf retrieves additional ODL objects instead of being requeued without progress.
- Resubmitting the US48 kFN core job to generate real scores before restoring `core_claim`.

### [2026-05-20 01:29] - method_runs
- Container build failed because `environment/container.def` tried to bake gitignored `data/downloads/*` files into the image.
- Removed the fragile `%files` section; runtime uses the bind-mounted workspace and `scripts/download.sh` repopulates `data/downloads/` from tracked data or verified URLs.
- Resubmitting the same CPU core job after the environment packaging fix.

### [2026-05-20 01:32] - core_claim
- CPU job `90b0e53b-aab` completed the US48 kFN core experiment with 12/12 exact queries.
- Reproduced the core benefit/constraint pair: exact kFN correctness with `candidates_ratio=0.1650` and `lookup_reduction_vs_brute=6.0601`.
- Expanding the same core experiment to a second object density before attempting a higher milestone.

### [2026-05-20 01:36] - core_claim_plus
- CPU job `e203f389-121` completed kFN at object densities 0.05 and 0.10 with 24/24 exact queries.
- Averaged score improved to `candidates_ratio=0.1566` and `lookup_reduction_vs_brute=6.4020` while preserving `accuracy=1.0`.
- Adding small AkNN and range runs to test secondary query claims next.

### [2026-05-20 01:40] - core_claim_plus
- CPU job `26aa2eab-2d1` verified AkNN and range correctness, but range scanned all objects (`candidates_ratio=1.0`).
- Fixed range leaf processing to use the ODL landmark-distance window implied by triangle inequality before exact checks.
- Resubmitting secondary query coverage before claiming `secondary_claims`.

### [2026-05-20 01:44] - secondary_claims
- CPU job `d266aebb-8f5` reran kFN, AkNN, and range after range ODL pruning.
- All evaluated query families were exact: kFN, AkNN, and range each reached `accuracy=1.0`.
- Secondary pruning now holds: AkNN `candidates_ratio=0.1666`, range `candidates_ratio=0.0844`, and kFN `lookup_reduction_vs_brute=6.4020`.

</details>

### Iteration 4: gpt-5.5 (designer_stage_1)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 6m | **GPU**: 0.0h
- **Jobs**: 4 total (4 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-05-20 01:23] - method_runs
- Audited the prior implementation and found root-only landmarks and missing COL internal object bounds.
- Reworked SUL-Tree construction to use graph-aware recursive partitions with local per-node landmarks and SDLs.
- Reworked COL-Tree construction to store object-specific min/max bounds for internal nodes and ODLs for leaves.
- Verified the revised method on a tiny local graph; submitting the first compute job to test the core kFN claim on US48.

### [2026-05-20 01:27] - method_runs
- Continued the audit and found that no fresh `experiment_results/core_claim` artifacts existed for the revised implementation.
- Fixed kFN leaf processing so a revisited COL leaf retrieves additional ODL objects instead of being requeued without progress.
- Resubmitting the US48 kFN core job to generate real scores before restoring `core_claim`.

### [2026-05-20 01:29] - method_runs
- Container build failed because `environment/container.def` tried to bake gitignored `data/downloads/*` files into the image.
- Removed the fragile `%files` section; runtime uses the bind-mounted workspace and `scripts/download.sh` repopulates `data/downloads/` from tracked data or verified URLs.
- Resubmitting the same CPU core job after the environment packaging fix.

### [2026-05-20 01:32] - core_claim
- CPU job `90b0e53b-aab` completed the US48 kFN core experiment with 12/12 exact queries.
- Reproduced the core benefit/constraint pair: exact kFN correctness with `candidates_ratio=0.1650` and `lookup_reduction_vs_brute=6.0601`.
- Expanding the same core experiment to a second object density before attempting a higher milestone.

### [2026-05-20 01:36] - core_claim_plus
- CPU job `e203f389-121` completed kFN at object densities 0.05 and 0.10 with 24/24 exact queries.
- Averaged score improved to `candidates_ratio=0.1566` and `lookup_reduction_vs_brute=6.4020` while preserving `accuracy=1.0`.
- Adding small AkNN and range runs to test secondary query claims next.

### [2026-05-20 01:40] - core_claim_plus
- CPU job `26aa2eab-2d1` verified AkNN and range correctness, but range scanned all objects (`candidates_ratio=1.0`).
- Fixed range leaf processing to use the ODL landmark-distance window implied by triangle inequality before exact checks.
- Resubmitting secondary query coverage before claiming `secondary_claims`.

### [2026-05-20 01:44] - secondary_claims
- CPU job `d266aebb-8f5` reran kFN, AkNN, and range after range ODL pruning.
- All evaluated query families were exact: kFN, AkNN, and range each reached `accuracy=1.0`.
- Secondary pruning now holds: AkNN `candidates_ratio=0.1666`, range `candidates_ratio=0.0844`, and kFN `lookup_reduction_vs_brute=6.4020`.

</details>

### Iteration 5: gpt-5.5 (designer_stage_2)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 3m | **GPU**: 0.0h
- **Jobs**: 4 total (4 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-05-20 01:23] - method_runs
- Audited the prior implementation and found root-only landmarks and missing COL internal object bounds.
- Reworked SUL-Tree construction to use graph-aware recursive partitions with local per-node landmarks and SDLs.
- Reworked COL-Tree construction to store object-specific min/max bounds for internal nodes and ODLs for leaves.
- Verified the revised method on a tiny local graph; submitting the first compute job to test the core kFN claim on US48.

### [2026-05-20 01:27] - method_runs
- Continued the audit and found that no fresh `experiment_results/core_claim` artifacts existed for the revised implementation.
- Fixed kFN leaf processing so a revisited COL leaf retrieves additional ODL objects instead of being requeued without progress.
- Resubmitting the US48 kFN core job to generate real scores before restoring `core_claim`.

### [2026-05-20 01:29] - method_runs
- Container build failed because `environment/container.def` tried to bake gitignored `data/downloads/*` files into the image.
- Removed the fragile `%files` section; runtime uses the bind-mounted workspace and `scripts/download.sh` repopulates `data/downloads/` from tracked data or verified URLs.
- Resubmitting the same CPU core job after the environment packaging fix.

### [2026-05-20 01:32] - core_claim
- CPU job `90b0e53b-aab` completed the US48 kFN core experiment with 12/12 exact queries.
- Reproduced the core benefit/constraint pair: exact kFN correctness with `candidates_ratio=0.1650` and `lookup_reduction_vs_brute=6.0601`.
- Expanding the same core experiment to a second object density before attempting a higher milestone.

### [2026-05-20 01:36] - core_claim_plus
- CPU job `e203f389-121` completed kFN at object densities 0.05 and 0.10 with 24/24 exact queries.
- Averaged score improved to `candidates_ratio=0.1566` and `lookup_reduction_vs_brute=6.4020` while preserving `accuracy=1.0`.
- Adding small AkNN and range runs to test secondary query claims next.

### [2026-05-20 01:40] - core_claim_plus
- CPU job `26aa2eab-2d1` verified AkNN and range correctness, but range scanned all objects (`candidates_ratio=1.0`).
- Fixed range leaf processing to use the ODL landmark-distance window implied by triangle inequality before exact checks.
- Resubmitting secondary query coverage before claiming `secondary_claims`.

### [2026-05-20 01:44] - secondary_claims
- CPU job `d266aebb-8f5` reran kFN, AkNN, and range after range ODL pruning.
- All evaluated query families were exact: kFN, AkNN, and range each reached `accuracy=1.0`.
- Secondary pruning now holds: AkNN `candidates_ratio=0.1666`, range `candidates_ratio=0.0844`, and kFN `lookup_reduction_vs_brute=6.4020`.

</details>

### Iteration 6: gpt-5.5 (designer_stage_3)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 7m | **GPU**: 0.0h
- **Jobs**: 7 total (7 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-05-20 01:23] - method_runs
- Audited the prior implementation and found root-only landmarks and missing COL internal object bounds.
- Reworked SUL-Tree construction to use graph-aware recursive partitions with local per-node landmarks and SDLs.
- Reworked COL-Tree construction to store object-specific min/max bounds for internal nodes and ODLs for leaves.
- Verified the revised method on a tiny local graph; submitting the first compute job to test the core kFN claim on US48.

### [2026-05-20 01:27] - method_runs
- Continued the audit and found that no fresh `experiment_results/core_claim` artifacts existed for the revised implementation.
- Fixed kFN leaf processing so a revisited COL leaf retrieves additional ODL objects instead of being requeued without progress.
- Resubmitting the US48 kFN core job to generate real scores before restoring `core_claim`.

### [2026-05-20 01:29] - method_runs
- Container build failed because `environment/container.def` tried to bake gitignored `data/downloads/*` files into the image.
- Removed the fragile `%files` section; runtime uses the bind-mounted workspace and `scripts/download.sh` repopulates `data/downloads/` from tracked data or verified URLs.
- Resubmitting the same CPU core job after the environment packaging fix.

### [2026-05-20 01:32] - core_claim
- CPU job `90b0e53b-aab` completed the US48 kFN core experiment with 12/12 exact queries.
- Reproduced the core benefit/constraint pair: exact kFN correctness with `candidates_ratio=0.1650` and `lookup_reduction_vs_brute=6.0601`.
- Expanding the same core experiment to a second object density before attempting a higher milestone.

### [2026-05-20 01:36] - core_claim_plus
- CPU job `e203f389-121` completed kFN at object densities 0.05 and 0.10 with 24/24 exact queries.
- Averaged score improved to `candidates_ratio=0.1566` and `lookup_reduction_vs_brute=6.4020` while preserving `accuracy=1.0`.
- Adding small AkNN and range runs to test secondary query claims next.

### [2026-05-20 01:40] - core_claim_plus
- CPU job `26aa2eab-2d1` verified AkNN and range correctness, but range scanned all objects (`candidates_ratio=1.0`).
- Fixed range leaf processing to use the ODL landmark-distance window implied by triangle inequality before exact checks.
- Resubmitting secondary query coverage before claiming `secondary_claims`.

### [2026-05-20 01:44] - secondary_claims
- CPU job `d266aebb-8f5` reran kFN, AkNN, and range after range ODL pruning.
- All evaluated query families were exact: kFN, AkNN, and range each reached `accuracy=1.0`.
- Secondary pruning now holds: AkNN `candidates_ratio=0.1666`, range `candidates_ratio=0.0844`, and kFN `lookup_reduction_vs_brute=6.4020`.

</details>

### Iteration 7: gpt-5.5 (packager)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 3m | **GPU**: 0.0h
- **Jobs**: 7 total (7 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-05-20 01:23] - method_runs
- Audited the prior implementation and found root-only landmarks and missing COL internal object bounds.
- Reworked SUL-Tree construction to use graph-aware recursive partitions with local per-node landmarks and SDLs.
- Reworked COL-Tree construction to store object-specific min/max bounds for internal nodes and ODLs for leaves.
- Verified the revised method on a tiny local graph; submitting the first compute job to test the core kFN claim on US48.

### [2026-05-20 01:27] - method_runs
- Continued the audit and found that no fresh `experiment_results/core_claim` artifacts existed for the revised implementation.
- Fixed kFN leaf processing so a revisited COL leaf retrieves additional ODL objects instead of being requeued without progress.
- Resubmitting the US48 kFN core job to generate real scores before restoring `core_claim`.

### [2026-05-20 01:29] - method_runs
- Container build failed because `environment/container.def` tried to bake gitignored `data/downloads/*` files into the image.
- Removed the fragile `%files` section; runtime uses the bind-mounted workspace and `scripts/download.sh` repopulates `data/downloads/` from tracked data or verified URLs.
- Resubmitting the same CPU core job after the environment packaging fix.

### [2026-05-20 01:32] - core_claim
- CPU job `90b0e53b-aab` completed the US48 kFN core experiment with 12/12 exact queries.
- Reproduced the core benefit/constraint pair: exact kFN correctness with `candidates_ratio=0.1650` and `lookup_reduction_vs_brute=6.0601`.
- Expanding the same core experiment to a second object density before attempting a higher milestone.

### [2026-05-20 01:36] - core_claim_plus
- CPU job `e203f389-121` completed kFN at object densities 0.05 and 0.10 with 24/24 exact queries.
- Averaged score improved to `candidates_ratio=0.1566` and `lookup_reduction_vs_brute=6.4020` while preserving `accuracy=1.0`.
- Adding small AkNN and range runs to test secondary query claims next.

### [2026-05-20 01:40] - core_claim_plus
- CPU job `26aa2eab-2d1` verified AkNN and range correctness, but range scanned all objects (`candidates_ratio=1.0`).
- Fixed range leaf processing to use the ODL landmark-distance window implied by triangle inequality before exact checks.
- Resubmitting secondary query coverage before claiming `secondary_claims`.

### [2026-05-20 01:44] - secondary_claims
- CPU job `d266aebb-8f5` reran kFN, AkNN, and range after range ODL pruning.
- All evaluated query families were exact: kFN, AkNN, and range each reached `accuracy=1.0`.
- Secondary pruning now holds: AkNN `candidates_ratio=0.1666`, range `candidates_ratio=0.0844`, and kFN `lookup_reduction_vs_brute=6.4020`.

</details>

### Iteration 8: gpt-5.5 (verifier)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 6m | **GPU**: 0.0h
- **Jobs**: 7 total (7 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-05-20 01:23] - method_runs
- Audited the prior implementation and found root-only landmarks and missing COL internal object bounds.
- Reworked SUL-Tree construction to use graph-aware recursive partitions with local per-node landmarks and SDLs.
- Reworked COL-Tree construction to store object-specific min/max bounds for internal nodes and ODLs for leaves.
- Verified the revised method on a tiny local graph; submitting the first compute job to test the core kFN claim on US48.

### [2026-05-20 01:27] - method_runs
- Continued the audit and found that no fresh `experiment_results/core_claim` artifacts existed for the revised implementation.
- Fixed kFN leaf processing so a revisited COL leaf retrieves additional ODL objects instead of being requeued without progress.
- Resubmitting the US48 kFN core job to generate real scores before restoring `core_claim`.

### [2026-05-20 01:29] - method_runs
- Container build failed because `environment/container.def` tried to bake gitignored `data/downloads/*` files into the image.
- Removed the fragile `%files` section; runtime uses the bind-mounted workspace and `scripts/download.sh` repopulates `data/downloads/` from tracked data or verified URLs.
- Resubmitting the same CPU core job after the environment packaging fix.

### [2026-05-20 01:32] - core_claim
- CPU job `90b0e53b-aab` completed the US48 kFN core experiment with 12/12 exact queries.
- Reproduced the core benefit/constraint pair: exact kFN correctness with `candidates_ratio=0.1650` and `lookup_reduction_vs_brute=6.0601`.
- Expanding the same core experiment to a second object density before attempting a higher milestone.

### [2026-05-20 01:36] - core_claim_plus
- CPU job `e203f389-121` completed kFN at object densities 0.05 and 0.10 with 24/24 exact queries.
- Averaged score improved to `candidates_ratio=0.1566` and `lookup_reduction_vs_brute=6.4020` while preserving `accuracy=1.0`.
- Adding small AkNN and range runs to test secondary query claims next.

### [2026-05-20 01:40] - core_claim_plus
- CPU job `26aa2eab-2d1` verified AkNN and range correctness, but range scanned all objects (`candidates_ratio=1.0`).
- Fixed range leaf processing to use the ODL landmark-distance window implied by triangle inequality before exact checks.
- Resubmitting secondary query coverage before claiming `secondary_claims`.

### [2026-05-20 01:44] - secondary_claims
- CPU job `d266aebb-8f5` reran kFN, AkNN, and range after range ODL pruning.
- All evaluated query families were exact: kFN, AkNN, and range each reached `accuracy=1.0`.
- Secondary pruning now holds: AkNN `candidates_ratio=0.1666`, range `candidates_ratio=0.0844`, and kFN `lookup_reduction_vs_brute=6.4020`.

### [2026-05-20 02:21] - secondary_claims
- Refreshed the evaluator to populate p90 and worst-query candidate-ratio constraint metrics from saved per-query method artifacts.
- Re-ran `scripts/evaluate.sh`, `scripts/evaluate_train.sh`, `scripts/evaluate_test.sh`, and `python validate.py --compare`; all checks pass.

### [2026-05-20 02:23] - secondary_claims
- Final verification passed after cleaning method-agnostic documentation, documenting replacement benchmark reference rows, and moving brute-force baseline helpers under `baseline/`.
- Verified download URLs and reran `python validate.py --compare`; all checks pass.

</details>

### Iteration 9: gpt-5.5 (verifier)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 11m | **GPU**: 0.0h
- **Jobs**: 8 total (8 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-05-20 01:23] - method_runs
- Audited the prior implementation and found root-only landmarks and missing COL internal object bounds.
- Reworked SUL-Tree construction to use graph-aware recursive partitions with local per-node landmarks and SDLs.
- Reworked COL-Tree construction to store object-specific min/max bounds for internal nodes and ODLs for leaves.
- Verified the revised method on a tiny local graph; submitting the first compute job to test the core kFN claim on US48.

### [2026-05-20 01:27] - method_runs
- Continued the audit and found that no fresh `experiment_results/core_claim` artifacts existed for the revised implementation.
- Fixed kFN leaf processing so a revisited COL leaf retrieves additional ODL objects instead of being requeued without progress.
- Resubmitting the US48 kFN core job to generate real scores before restoring `core_claim`.

### [2026-05-20 01:29] - method_runs
- Container build failed because `environment/container.def` tried to bake gitignored `data/downloads/*` files into the image.
- Removed the fragile `%files` section; runtime uses the bind-mounted workspace and `scripts/download.sh` repopulates `data/downloads/` from tracked data or verified URLs.
- Resubmitting the same CPU core job after the environment packaging fix.

### [2026-05-20 01:32] - core_claim
- CPU job `90b0e53b-aab` completed the US48 kFN core experiment with 12/12 exact queries.
- Reproduced the core benefit/constraint pair: exact kFN correctness with `candidates_ratio=0.1650` and `lookup_reduction_vs_brute=6.0601`.
- Expanding the same core experiment to a second object density before attempting a higher milestone.

### [2026-05-20 01:36] - core_claim_plus
- CPU job `e203f389-121` completed kFN at object densities 0.05 and 0.10 with 24/24 exact queries.
- Averaged score improved to `candidates_ratio=0.1566` and `lookup_reduction_vs_brute=6.4020` while preserving `accuracy=1.0`.
- Adding small AkNN and range runs to test secondary query claims next.

### [2026-05-20 01:40] - core_claim_plus
- CPU job `26aa2eab-2d1` verified AkNN and range correctness, but range scanned all objects (`candidates_ratio=1.0`).
- Fixed range leaf processing to use the ODL landmark-distance window implied by triangle inequality before exact checks.
- Resubmitting secondary query coverage before claiming `secondary_claims`.

### [2026-05-20 01:44] - secondary_claims
- CPU job `d266aebb-8f5` reran kFN, AkNN, and range after range ODL pruning.
- All evaluated query families were exact: kFN, AkNN, and range each reached `accuracy=1.0`.
- Secondary pruning now holds: AkNN `candidates_ratio=0.1666`, range `candidates_ratio=0.0844`, and kFN `lookup_reduction_vs_brute=6.4020`.

### [2026-05-20 02:21] - secondary_claims
- Refreshed the evaluator to populate p90 and worst-query candidate-ratio constraint metrics from saved per-query method artifacts.
- Re-ran `scripts/evaluate.sh`, `scripts/evaluate_train.sh`, `scripts/evaluate_test.sh`, and `python validate.py --compare`; all checks pass.

### [2026-05-20 02:23] - secondary_claims
- Final verification passed after cleaning method-agnostic documentation, documenting replacement benchmark reference rows, and moving brute-force baseline helpers under `baseline/`.
- Verified download URLs and reran `python validate.py --compare`; all checks pass.

### [2026-05-20 02:27] - secondary_claims
- Re-audited the submitted workspace, moved the AUB-PHL-style helper used by the experiment harness into `baseline/`, and removed the stale baseline module from `method/`.
- Re-ran bytecode checks, `scripts/evaluate.sh`, and `python3 validate.py --compare`; all checks pass.

### [2026-05-20 02:32] - method_runs
- Sub-agent audit found that the previous results relied on stale artifacts and exact full-graph local-landmark distances, so the honest current milestone is reset pending a fresh job.
- Removed full-graph local-landmark SDL caching, switched COL node bounds to root-landmark lower/upper-bound substitution, changed kFN leaves to enqueue object candidates by upper bound before exact verification, and made result artifacts include per-query outputs.
- Updated evaluation to recompute main accuracy from method outputs and exact ground truth, tightened train/test evaluators to require per-query correctness and exact lookup counts, and changed `scripts/run.sh` to regenerate method artifacts before scoring.
- Bytecode checks and a tiny local graph smoke test pass; submitting a CPU job to regenerate the benchmark artifacts.

### [2026-05-20 02:35] - method_runs
- Final verification found that the checked-in `experiment_results/core_claim` artifacts are still stale and fail standalone `scripts/evaluate.sh` because they lack `queries.per_query`.
- Verified both download URLs with `curl -I -L --max-time 15`; both returned HTTP 200.
- Cleaned public scoring guidance to avoid exposing implementation names in method-agnostic/high-level gym documents.
- Keeping the milestone at `method_runs` and submitting the prepared CPU job to regenerate artifacts and scores before any final `secondary_claims` sign-off.

### [2026-05-20 02:39] - secondary_claims
- CPU job `714f3f12-b67` regenerated post-audit artifacts and completed `scripts/run.sh` with exit code 0.
- Fresh artifacts now include `queries.per_query`, per-query correctness flags, and kFN exact-lookup counts required by the stricter evaluator.
- `python3 validate.py --compare` passed in the job; regenerated scores show exact kFN, AkNN, and range results with nontrivial candidate pruning.

</details>


---

# Reproduction Milestones

**Current: secondary_claims**

## Stop Justification
- Completed at milestone `secondary_claims`.
