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
