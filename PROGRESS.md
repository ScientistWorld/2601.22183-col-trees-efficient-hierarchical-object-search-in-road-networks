# Progress

## What Works

- Paper analysis and briefing files are in place for the COL-Tree/SUL-Tree road-network POI search paper.
- Data download script provides the US48 road graph and Pennsylvania road graph fallback.
- SUL-Tree now builds graph-aware recursive partitions and computes local per-node landmark SDLs.
- COL-Tree now builds POI-specific internal min/max landmark bounds and leaf ODLs.
- kFN, AkNN, and range query entry points run on a small local smoke graph and match exact results when ties are handled correctly.
- `scripts/run.sh` submits the core kFN reproduction and calls `scripts/evaluate.sh` to refresh `scoring/scores.json`.
- kFN leaf processing now advances on every revisited COL leaf, avoiding a stale requeue state after initialization.
- `environment/container.def` no longer tries to copy gitignored download artifacts into the container; data is prepared by `scripts/download.sh` in the bind-mounted workspace.

## Results Achieved

- Current verified milestone is `secondary_claims`.
- CPU job `90b0e53b-aab` ran the revised COL/SUL kFN implementation on US48 at object density 0.05 with 6,307 objects and 12 queries.
- Reproduced score: `accuracy=1.0`, `candidates_ratio=0.165015`, `lookup_reduction_vs_brute=6.060053`, `sul_time_s=23.6116`, `col_time_s=1.0631`.
- The result is weaker than the paper's reported `candidates_ratio=0.01` and `lookup_reduction_vs_brute=100`, but it supports the core claim at reduced scale: exact kFN answers while verifying a fraction of the object set.
- CPU job `e203f389-121` expanded kFN to densities 0.05 and 0.10 with 24/24 exact queries. Averaged scoring is `accuracy=1.0`, `candidates_ratio=0.156648`, `lookup_reduction_vs_brute=6.402002`.
- CPU job `26aa2eab-2d1` added AkNN and range runs. AkNN reached `accuracy=1.0` with `candidates_ratio=0.166640`; range reached `accuracy=1.0` but scanned all objects with `candidates_ratio=1.0`, so it does not yet support the secondary efficiency claim.
- CPU job `d266aebb-8f5` reran secondary queries after range ODL pruning. Final scores are kFN `accuracy=1.0`, `candidates_ratio=0.156648`, `lookup_reduction_vs_brute=6.402002`; AkNN `accuracy=1.0`, `candidates_ratio=0.166640`; range `accuracy=1.0`, `candidates_ratio=0.084351`; preprocessing `sul_time_s=19.5664`, `col_time_s=0.4934`.
- An earlier resubmission did not reach the job stage because the container build attempted to copy `data/downloads/road-usroads-48.mtx`, which is not present in a fresh build checkout. The packaging issue was fixed before job `90b0e53b-aab`.

## Deviations From Paper

- Paper dataset: DIMACS continental US road network with OSM POIs.
- Reproduction dataset: US48 road graph with synthetic POI subsets sampled from graph vertices, because the full paper dataset and POI files are not available in this workspace.
- Paper partitioner: METIS-style graph partitioning.
- Reproduction partitioner: deterministic multi-source BFS graph partitioning, preserving recursive graph-aware subgraphs without external OS-level dependencies.
- Paper distance oracle: PHL for exact distance verification.
- Reproduction distance verification: Dijkstra on the shipped graph. This preserves exactness but changes wall-clock behavior, so scoring emphasizes candidate and lookup reduction.

## What Remains

- Higher milestones would require broader coverage of the paper's full experimental tables and the original DIMACS/OSM POI setup. This workspace instead provides a reusable, smaller US48 benchmark with the paper's core and secondary query mechanisms exercised.

## Issues Encountered

- The inherited implementation used root landmarks for every SUL node, which was not faithful to the paper.
- Internal COL nodes previously lacked object-specific min/max landmark distances, weakening or breaking pruning.
- Correctness checks previously compared sets directly, which falsely rejected valid top-k ties. The experiment code now accepts any exact tied top-k result.
- kFN leaf nodes were previously only advanced on their first priority-queue visit; that control-flow bug is fixed before the next core run.
- The container definition previously baked workspace files, including gitignored downloads, into the image despite the workspace being bind-mounted at runtime. This caused the build failure and has been removed.
- Range leaf processing scanned the full ODL even when the landmark triangle lower bound excluded most objects. It now restricts exact checks to the feasible sorted-distance window.
