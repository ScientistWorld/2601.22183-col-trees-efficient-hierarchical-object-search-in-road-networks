# Scientist Constraints

## Index Structure
The scientist must build and use hierarchical index structures (SUL-Tree and COL-Tree) on the road network graph. Precomputing ALL-PAIRS distances or storing full distance matrices is NOT allowed — the contribution is the hierarchical landmark-based index. The index must use landmark distances for pruning.

## Dataset
The scientist must use the provided road network (US48 with 126K vertices or Pennsylvania with 1M+ vertices). No external road networks or additional geographic data. POI sets must be subsets of graph vertices.

## Algorithm
The scientist must implement the core algorithmic approach: hierarchical partitioning with landmark-based lower/upper bounds for query pruning. Switching to fundamentally different paradigms (e.g., Hub Labels, SILC, RIPPER) is out of scope — the paper's contribution is the COL-Tree/SUL-Tree landmark-based approach.

## Correctness
All query results must match exact ground truth. A scientist who improves query time by sacrificing accuracy should score WORSE.

## Compliance Checklist
- [ ] Index uses landmark-based lower/upper bounds for pruning
- [ ] No precomputed all-pairs distance matrix or full distance oracle
- [ ] Results are 100% correct (verified against brute force)
- [ ] Uses the provided road network dataset (no external networks)

