# Method: COL-Tree and SUL-Tree for Hierarchical POI Search

This file describes the paper's method and how the reproduction implements it (`method/build.py`,
`method/solver.py`). The problem and the measurement are in `problem.md` and `evaluation.md`.

## SUL-Tree (road-network index, paper Section 3.1)

- The road network is recursively partitioned into `b` disjoint, similar-sized subgraphs until a subgraph
  has at most `alpha` vertices. The paper uses METIS and allows any partitioner that produces
  similar-sized subgraphs. The reproduction uses recursive median bisection of the vertex coordinates
  (`method/build.py`), which gives balanced, spatially compact subgraphs. These subgraphs are not always
  connected inside, so the distance-list construction can settle many outside vertices.
- The root node is the shared ALT index: 16 random landmarks with distances to every vertex (paper Section 9.1).
- Every other node selects `m` local landmarks among its own vertices. The four policies of Section 3.3.1
  are implemented: Random, Furthest Border, Slice-Based Furthest Border and Border Minmax.
- For each landmark of a node, a Subgraph Distance List (SDL) holds the distance to every vertex of the
  node's subgraph. In this gym the submitted structure only fixes the hierarchy and the landmarks. The
  evaluator computes the SDLs on its own network.

## COL-Tree (object index, Section 3.2)

For a query's object set, the COL-Tree is the SUL-Tree compacted at the first node holding at most
`lambda` objects. Internal COL nodes keep, per landmark, the minimum and maximum landmark distance over
their objects. COL leaves keep one Object Distance List (ODL) per landmark: the landmark distances of
the leaf's objects, sorted. In the gym, node summaries and ODL reads (`nodes`, `peek`, `bisect`) are the
COL-Tree's bookkeeping. `get` retrieves objects from an ODL.

## Bounds (Section 3.3)

- Per landmark, for all objects of a node: Eq. (4) lower bound and Eq. (6) upper bound, from `d(l, q)`
  and the node's min/max landmark distances.
- `d(l, q)` is exact when `q` lies in the landmark's subgraph. Otherwise it is bounded through the
  landmarks of the root and of the lowest common ancestor (Eq. 7).
- Alternate bound from the root landmarks' min/max (`M_R`).
- `--bounds all` (an option, not the paper's default) also uses every ancestor's landmarks.

## Query algorithms (Sections 4-6)

- **AkNN** (Algorithm 1): best-first search keyed by the aggregate lower bound (Lemma 1).
  - A leaf's ODL is chosen by the largest average distance to Q.
  - The search starts at the ODL position given by Lemma 2 (sum: median) or Lemma 3 (max: midpoint), then
    moves left and right (convexity). Objects get their own bound from the leaf landmark and the root
    landmarks before an exact distance is computed.
- **kFN** (Algorithm 2): best-first search keyed by the upper bound.
  - A leaf's ODL is chosen by the landmark closest to q and scanned from its far end.
  - It stops when no remaining bound exceeds the k-th best exact distance.
- **Range** (Algorithm 3): stack traversal.
  - Subtrees whose upper bound is within r are reported whole. Subtrees whose lower bound exceeds r are pruned.
  - Leaves report the ODL prefix confirmed by upper bound. They verify the window allowed by the lower bound.

## Parameters (paper Table 8, alpha = 1024, lambda = 256)

| Query | b | m | Landmark policy | Entries per vertex |
|---|---:|---:|---|---:|
| kFN | 4 | 4 | Slice-Based Furthest Border | 16 + 6 levels x 4 = 40 |
| AkNN | 8 | 2 | Random | 16 + 4 levels x 2 = 24 |
| Range | 8 | 2 | Border Minmax | 16 + 4 levels x 2 = 24 |

`experiment_results/colt` uses these per-query settings. `experiment_results/colt_default` uses b=8,
m=2, Random for every query type (the paper's default).

## Key claims

1. Landmark bounds over a subgraph hierarchy prune most objects without retrieving them individually,
   for AkNN, kFN and range queries.
2. Convexity of sum/max aggregates lets one binary search per leaf start AkNN retrieval at the best object.
3. kFN can be answered by incremental retrieval by upper bound, which no expansion-based or
   Euclidean-bound method supports.
4. The index costs little more than an ALT index of the same size.
