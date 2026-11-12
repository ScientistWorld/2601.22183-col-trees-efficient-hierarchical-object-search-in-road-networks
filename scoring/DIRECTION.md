# Research Direction

## Research Problem
Answer exact POI search queries on a large road network: aggregate k nearest neighbors, k farthest neighbors and range.
Exact network distances are expensive, and object sets change from query to query.
A method therefore needs a road-network index that lets it rule objects in or out without evaluating each one.

## Direction
Work on exact, index-based road-network object search under a fixed index budget.
Successful submissions retrieve fewer individual objects and compute fewer exact distances, while staying exact and within the index size and construction-work caps.

## Approach Scope
The scientist may change:
- How the road network is organised for the index (hierarchy shape, partitioning)
- Where index landmarks are placed and how many each node gets, within budget
- Bound computation, pruning rules and traversal order in the solver
- Batching and candidate verification strategy

## Out of Bounds
- Exceeding the index budget or bypassing the protocol (for example, reading travel times or object sets from outside the protocol)
- Inexact answers
- External road networks, map APIs or geographic databases
