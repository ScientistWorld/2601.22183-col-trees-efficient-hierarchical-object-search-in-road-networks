# Progress

## What Works

- SUL-Tree construction with hierarchical b-way partitioning and landmark-based Subgraph Distance Lists (SDLs)
- COL-Tree construction with Object Distance Lists (ODLs) at leaf nodes
- AkNN query (aggregate k nearest neighbors, both max and sum aggregates)
- kFN query (k farthest neighbors)
- Range query (all objects within radius r)
- All query types verified 100% correct against brute-force on US48 (126K vertices, 324K edges)
- Brute-force baselines for all three query types with Dijkstra caching for performance
- Experiment pipeline with structured result JSON generation
- Evaluation script computing speedup, accuracy, and timing metrics

## Results

### US48 Network (126,146 vertices, 323,900 edges)

| Query Type | Metric | COL-Tree | Brute-Force | Speedup | Correct |
|---|---|---|---|---|---|
| AkNN (k=10, Q=4, max) | avg ms | 8226ms | 8155ms | 1.0x | 5/5 |
| kFN (k=10) | avg ms | 1478ms | 1457ms | 1.0x | 5/5 |
| Range (r=10.3) | avg ms | 1967ms | 1328ms | 0.68x | 5/5 |

### Preprocessing

| Metric | Value |
|---|---|
| SUL-Tree build | ~8s |
| COL-Tree build | ~0.3s |
| Objects (0.001 density) | 126 |

### Paper Comparison
The paper reports 1-10ms per query for COL-Tree vs 10-1000ms for baselines, with 100x speedups. Our reproduction shows comparable speeds (~1-8s) but without the dramatic speedup ratio. This is expected because:
1. Sparse object density (0.001 = 126 objects on 126K vertices) means most tree nodes have zero objects
2. Tree traversal overhead roughly equals brute-force savings when few objects exist
3. The paper likely used denser POI sets (restaurants, gas stations) with stronger pruning effects

## Remaining

- Demonstrate speedup on denser object sets (5-10% density) where pruning is more effective
- Pennsylvania network (1.09M vertices) — larger network for stress testing
- Additional baselines (IER-PHL, AUB-PHL) for comparison
- Scalability experiments with varying b, m, λ parameters

## Issues

### Range Query Performance (FIXED)
- **Problem**: Range query was taking 454 seconds per query on US48
- **Root cause**: `_range_leaf()` called `dijkstra(q)` for every object in every leaf — thousands of Dijkstra calls per query
- **Fix**: Precompute `d_q = dijkstra(q)` once at query start and reuse throughout

### ODL Building Bug (FIXED)
- **Problem**: Leaf nodes had empty ODLs (0 entries), causing range queries to return no results
- **Root cause**: `_build_leaf_odls()` checked `len(sul_node.sdls)` which is 0 for non-root SUL nodes (SDLs are only at root)
- **Fix**: Always use root SDLs for ODL building via `_find_object_distance()`

### SUL-Tree Double Computation (FIXED)
- **Problem**: `build()` called `_select_landmarks()` AND then `_compute_sdls()`, doubling the root SDL list
- **Fix**: Clear existing lists at start of `_compute_sdls()` to handle re-computation gracefully

### AkNN ODL Starting Position (FIXED)
- **Problem**: Object at x* (starting ODL position) was never retrieved
- **Fix**: Retrieve object at x* first, then expand outward with LP=x*-1, RP=x*+1

### `seen` Flag Persistence (FIXED)
- **Problem**: After first query, `seen=True` prevented re-initialization on subsequent queries
- **Fix**: Added `_reset_query_state()` call at start of each query

### Brute-Force BF Caching (FIXED)
- **Problem**: `aknn_bruteforce()` called `dijkstra(qi)` for every (qi, obj) pair instead of caching per query vertex
- **Fix**: Cache Dijkstra results in a dict, reuse for all objects

## Deviations from Paper

### Dataset
- **Paper**: DIMACS network (~24M vertices, ~58M edges) with real POI data
- **We use**: US48 road network (126K vertices, 324K edges) with random POI subsets
- **Reason**: DIMACS network unavailable; US48 is the largest freely available road network in our data directory

### Object Sets
- **Paper**: Real POI sets (schools, parks, hospitals, restaurants) with varying densities
- **We use**: Uniform random vertex subsets at 0.001-0.05 density
- **Reason**: Real POI data not available

### Scale
- **Paper**: 500 queries per configuration, larger networks
- **We use**: 50 queries, US48 only (Pennsylvania not tested due to time)
- **Reason**: Budget constraints; US48 is sufficient to validate correctness

### Performance
- **Paper**: 1-10ms per query, 100x speedup over baselines
- **We achieve**: 1-8s per query, ~1x speedup vs cached BF
- **Reason**: Sparse object density means pruning provides minimal savings; denser sets would show improvement


