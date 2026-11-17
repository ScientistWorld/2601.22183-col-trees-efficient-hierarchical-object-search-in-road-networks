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

Score every POI p by g(p) = agg( d(q, p) for q ∈ Q ) and return the k POIs with the smallest g(p).
Ties at the k-th value may be broken arbitrarily.

For `sum`, g(p) is the total distance from all query vertices to p (e.g. a meeting point minimising total travel).
For `max`, g(p) is the distance from the farthest query vertex to p (minimising the latest arrival).

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

This environment targets the three query types above. The road network is the paper's own dataset (North-West US subset of the DIMACS travel-time network, 1.09M vertices) with its real OpenStreetMap POI categories. The object set changes with every query; it may cover the whole network or only one region of it, and queries can come from anywhere on the network. Exact network distances are only available from the evaluator, which counts them; see `briefing/evaluation.md`.
