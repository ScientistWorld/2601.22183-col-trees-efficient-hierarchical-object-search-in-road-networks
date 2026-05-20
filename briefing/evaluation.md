# Evaluation Plan: COL-Tree Reproduction

## Dataset

- **Paper road network**: DIMACS US road network (~23.9 million vertices, ~57.7 million edges)
- **Reproduction road network**: US48 road graph shipped in `data/downloads/`, with synthetic POI subsets sampled from vertices
- **Paper POI sets**: Schools, parks, hospitals, fast food, post offices, hotels, universities, and courthouses
- **Query sets**: Query vertices sampled from the road network according to the protocols described below

## Performance Metrics

### Primary Metrics

1. **Number of Network Distance Computations**
   - Count of actual shortest-path computations (Dijkstra/BI-Dijkstra runs) performed during query answering
   - This is a key indicator of index efficiency and pruning power
   - Lower is better
   - Target: significantly fewer distance computations than baseline methods

2. **Number of Candidate Objects Retrieved**
   - Count of POIs examined or returned as candidates during query processing
   - Lower is better (indicates tighter pruning)

3. **Average Query Time (ms)**
   - Reported for diagnostics only. It is not the primary score because hardware and Python/C++ implementation differences dominate wall-clock comparisons.

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

- The paper uses 1000 queries per configuration. The reproduction uses smaller query counts for core jobs and validates every query against exact brute force.
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
