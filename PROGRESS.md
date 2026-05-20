# Progress

## What Works

- Paper analysis and briefing files are in place for the COL-Tree/SUL-Tree road-network POI search paper.
- Data download script provides the US48 road graph and Pennsylvania road graph fallback.
- SUL-Tree now builds graph-aware recursive partitions and computes local per-node landmark SDLs.
- COL-Tree now builds POI-specific internal min/max landmark bounds and leaf ODLs.
- kFN, AkNN, and range query entry points run on a small local smoke graph and match exact results when ties are handled correctly.
- `scripts/run.sh` submits the core kFN reproduction and calls `scripts/evaluate.sh` to refresh `scoring/scores.json`.
- kFN leaf processing now advances on every revisited COL leaf, avoiding a stale requeue state after initialization.

## Results Achieved

- Current verified milestone remains `method_runs`: the revised algorithm executes on a small local graph.
- The previous `scores.json` came from older artifacts and should be replaced by the submitted core-claim job before claiming `core_claim`.
- No fresh `experiment_results/core_claim` artifacts were present during the continuation audit, so the next CPU job is the source of truth for restoring the milestone.

## Deviations From Paper

- Paper dataset: DIMACS continental US road network with OSM POIs.
- Reproduction dataset: US48 road graph with synthetic POI subsets sampled from graph vertices, because the full paper dataset and POI files are not available in this workspace.
- Paper partitioner: METIS-style graph partitioning.
- Reproduction partitioner: deterministic multi-source BFS graph partitioning, preserving recursive graph-aware subgraphs without external OS-level dependencies.
- Paper distance oracle: PHL for exact distance verification.
- Reproduction distance verification: Dijkstra on the shipped graph. This preserves exactness but changes wall-clock behavior, so scoring emphasizes candidate and lookup reduction.

## What Remains

- Run the submitted US48 kFN core job and inspect whether COL-Tree achieves exact results with meaningful candidate reduction versus brute force/AUB.
- If the core result is weak, tune `lambda`, density, branch factor, and landmark count while preserving the COL/SUL algorithm.
- Extend evaluation to AkNN and range after the kFN core claim is supported.

## Issues Encountered

- The inherited implementation used root landmarks for every SUL node, which was not faithful to the paper.
- Internal COL nodes previously lacked object-specific min/max landmark distances, weakening or breaking pruning.
- Correctness checks previously compared sets directly, which falsely rejected valid top-k ties. The experiment code now accepts any exact tied top-k result.
- kFN leaf nodes were previously only advanced on their first priority-queue visit; that control-flow bug is fixed before the next core run.
